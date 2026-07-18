"""Specialist handoff request helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.agents import LocalAgent
from app.models.supervisor import AgentHandoffRequest, AgentRunResult, SupervisorRequest
from app.providers import ModelMessage


def _handoff_request(
    request: SupervisorRequest,
    target_agent_id: str,
    agent_results: Sequence[AgentRunResult],
) -> AgentHandoffRequest:
    return AgentHandoffRequest(
        original_user_input=request.user_input,
        context=(*request.messages, *_agent_result_context(agent_results)),
        target_agent_id=target_agent_id,
        specific_request=_specific_request(
            target_agent_id,
            request.user_input,
            request.agent_catalog,
        ),
    )


def _agent_result_context(
    agent_results: Sequence[AgentRunResult],
) -> tuple[ModelMessage, ...]:
    return tuple(
        ModelMessage(
            role="assistant",
            content=result.content,
            agent_name=result.agent_id,
        )
        for result in agent_results
    )


def _specific_request(
    target_agent_id: str,
    user_input: str,
    agent_catalog: Mapping[str, LocalAgent],
) -> str:
    if target_agent_id == "summarizer":
        return f"Summarize the available findings for this request: {user_input}"
    if target_agent_id == "visualizer":
        return f"Create a chart specification for this request: {user_input}"
    custom_agent = agent_catalog.get(target_agent_id)
    if custom_agent is not None:
        return (
            f"Use your configured prompt and tools to help with this request: "
            f"{user_input}"
        )
    return f"Help respond to this request: {user_input}"
