from __future__ import annotations

from google.adk.agents import Agent

from agent.app.agents.orchestrator import AgentOrchestrator
from agent.app.schemas.orchestration import AgentRequest, TrustedRequestContext


root_agent = Agent(
    name="streamlogic_orchestrator",
    model="gemini-2.0-flash",
    description="Orchestration shell for StreamLogic AI.",
    instruction=(
        "Coordinate the explicit QueryClassifier, routing matrix, and specialist subagent handoffs. "
        "Do not fabricate final recommendation outputs."
    ),
)


async def run_orchestrator(
    orchestrator: AgentOrchestrator,
    message: str,
    user_id: int = 1,
    session_id: str = "session",
):
    return await orchestrator.orchestrate(
        AgentRequest(
            message=message,
            context=TrustedRequestContext(user_id=user_id, session_id=session_id),
        )
    )
