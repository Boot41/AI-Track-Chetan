from __future__ import annotations

from google.adk.agents import Agent

from agent.app.agents.orchestrator import AgentOrchestrator
from agent.app.formatters import format_public_response
from agent.app.persistence.session import get_sessionmaker
from agent.app.schemas.orchestration import AgentRequest, TrustedRequestContext


async def orchestrate_query(
    message: str,
    user_id: int = 1,
    session_id: str = "session",
) -> dict[str, object]:
    orchestrator = AgentOrchestrator(get_sessionmaker())
    result = await orchestrator.orchestrate(
        AgentRequest(
            message=message,
            context=TrustedRequestContext(user_id=user_id, session_id=session_id),
        )
    )
    return format_public_response(result)


root_agent = Agent(
    name="streamlogic_orchestrator",
    model="gemini-2.5-flash",
    description="Orchestration shell for StreamLogic AI.",
    instruction=(
        "Use the orchestrate_query tool to run the explicit query classifier, routing matrix, "
        "and specialist subagent handoffs. Do not fabricate final recommendation outputs."
    ),
    tools=[orchestrate_query],
)


async def run_orchestrator(
    orchestrator: AgentOrchestrator,
    message: str,
    user_id: int = 1,
    session_id: str = "session",
) -> dict[str, object]:
    result = await orchestrator.orchestrate(
        AgentRequest(
            message=message,
            context=TrustedRequestContext(user_id=user_id, session_id=session_id),
        )
    )
    return format_public_response(result)
