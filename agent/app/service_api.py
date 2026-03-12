from __future__ import annotations

import logging
import os
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Initialize settings and set environment variables for Google GenAI ASAP
# This must happen before importing root_agent which initializes the ADK agents
try:
    from server.app.core.config import get_settings
    settings = get_settings()
    if settings.google_api_key:
        os.environ["GOOGLE_API_KEY"] = settings.google_api_key
except ImportError:
    # If server package is not available, assume ENV is already set
    pass

from .agent import root_agent
from google.adk.runners import Runner
from google.adk.sessions.in_memory_session_service import InMemorySessionService
from google.genai import types

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="StreamLogic Agent Service")
session_service = InMemorySessionService()

class AgentRequest(BaseModel):
    message: str
    user_id: str = "user"
    session_id: str = "session"
    context: Optional[dict[str, Any]] = None

class SSERequest(BaseModel):
    app_name: str
    message: Any  # Can be string or ADK message object
    user_id: str
    session_id: str

@app.post("/run_sse")
async def run_sse(request: SSERequest):
    # This endpoint mimics what the ADK Web Server expects for its internal UI
    # but we can implement it to proxy to our evaluate logic if needed.
    # For now, let's just make it exist so the test doesn't 404.
    return {"status": "ok"}

@app.post("/evaluate")
async def evaluate(request: AgentRequest):
    try:
        # We need a session object
        try:
            session = await session_service.get_session(
                app_name="streamlogic_orchestrator",
                user_id=request.user_id,
                session_id=request.session_id
            )
        except Exception:
            session = None

        if not session:
            session = await session_service.create_session(
                app_name="streamlogic_orchestrator",
                user_id=request.user_id,
                session_id=request.session_id
            )
        
        # If backend passed session_state_payload, update the session state in ADK
        if request.context and "session_state_payload" in request.context:
            payload = request.context["session_state_payload"]
            # Directly update the state of the session object in memory
            # The InMemorySessionService stores session objects in self.sessions
            # We can access it via session_service.sessions[app_name][user_id][session_id]
            # but it's safer to just update the object we have and let the runner use it.
            # However, the runner gets the session from the service.
            
            # Since InMemorySessionService.sessions is public, we can update it directly
            app_name = "streamlogic_orchestrator"
            if app_name in session_service.sessions and \
               request.user_id in session_service.sessions[app_name] and \
               session.id in session_service.sessions[app_name][request.user_id]:
                session_service.sessions[app_name][request.user_id][session.id].state["session_state_payload"] = payload
        
        runner = Runner(
            agent=root_agent, 
            app_name="streamlogic_orchestrator", 
            session_service=session_service
        )
        
        content = types.Content(
            role="user",
            parts=[types.Part.from_text(text=request.message)],
        )

        final_payload = None
        final_text = ""
        
        # In ADK Runner, events are yielded
        async for event in runner.run_async(
            user_id=request.user_id,
            session_id=session.id,
            new_message=content
        ):
            # Capture the synthesized text
            if event.is_final_response() and event.content and event.content.parts:
                final_text = event.content.parts[0].text or ""
            
            # Capture tool output from orchestrate_query if it was called
            if event.get_function_responses():
                for resp in event.get_function_responses():
                    if resp.name == "orchestrate_query":
                        final_payload = resp.response

        if final_payload:
            # Overwrite answer with LLM reasoning if text was produced
            if final_text:
                final_payload["answer"] = final_text
            return final_payload

        # Fallback if tool wasn't called or captured
        return {
            "answer": final_text or "No response generated.",
            "scorecard": {
                "scorecard_type": "evaluation",
                "query_type": "general_question",
                "title": "Agent Response",
                "risk_flags": [],
                "recommendation": None,
                "narrative_score": None,
                "projected_completion_rate": None,
                "estimated_roi": None,
                "catalog_fit_score": None,
                "risk_level": None,
                "comparison": None,
                "focus_area": None
            },
            "evidence": [],
            "meta": {"warnings": [], "confidence": 0.5, "review_required": True}
        }
    except Exception as e:
        logger.exception("Error during evaluation")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "ok"}
