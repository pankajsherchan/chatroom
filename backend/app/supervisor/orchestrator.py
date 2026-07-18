"""Provider-driven multi-agent supervisor orchestration."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Protocol

from app.agent_registry import is_specialist_agent_id
from app.models.supervisor import AgentRunResult, SupervisorRequest, SupervisorResponse
from app.providers import ModelMessage, ModelProvider
from app.routing import route_agent_ids, stable_specialist_order
from app.supervisor.evidence import (
    _artifacts_from_agent_results,
    _synthesize_agent_results,
    _synthesize_final_answer,
)
from app.supervisor.follow_ups import _run_supervisor_follow_ups
from app.supervisor.handoff import _handoff_request
from app.supervisor.team import allowed_specialist_ids
from app.supervisor.tool_runner import _run_custom_agent
from app.turn_report import TurnTrace


class Supervisor(Protocol):
    """Common interface implemented by supervisor orchestration strategies."""

    def run(self, request: SupervisorRequest) -> SupervisorResponse:
        """Run one supervised user turn and return the synthesized response."""
        ...


class ProviderSupervisor:
    """Supervisor implementation that asks a provider to choose specialists."""

    def __init__(self, provider: ModelProvider) -> None:
        self.provider = provider

    def run(self, request: SupervisorRequest) -> SupervisorResponse:
        trace = TurnTrace()
        trace.meta["user_input"] = request.user_input
        trace.meta["selected_agent_ids"] = list(request.selected_agent_ids)
        trace.meta["catalog_agent_ids"] = list(request.agent_catalog.keys())

        manager_messages = _manager_messages(request)
        response = self.provider.generate(manager_messages)
        routed_agent_ids, used_fallback = _agent_ids_from_provider_decision(
            response.content,
            request,
        )
        system_message = next(
            (message.content for message in manager_messages if message.role == "system"),
            "",
        )
        user_message = next(
            (message.content for message in manager_messages if message.role == "user"),
            "",
        )
        available = [
            {
                "id": agent_id,
                "name": agent.name,
                "description": agent.description,
                "tools": list(agent.tools),
            }
            for agent_id in allowed_specialist_ids(request)
            if (agent := request.agent_catalog.get(agent_id)) is not None
        ]
        trace.add(
            "manager",
            "Manager chose specialists",
            what_this_step_does=(
                "The supervisor manager asks the model which specialist agents "
                "should handle this user prompt. No tools run in this step — "
                "only routing."
            ),
            received_from_ui={
                "user_prompt": request.user_input,
                "conversation_team_agent_ids": list(request.selected_agent_ids),
                "prior_messages_in_request": len(request.messages),
            },
            available_specialists=available,
            manager_system_message=system_message,
            manager_user_message=user_message,
            provider_call={
                "method": "provider.generate(messages, tools=())",
                "tools_passed": [],
                "note": "Manager routing uses generate() with no tool schemas.",
            },
            raw_provider_content=response.content,
            decision={
                "chosen_agent_ids": list(routed_agent_ids),
                "used_keyword_routing_fallback": used_fallback,
                "fallback_meaning": (
                    "Provider JSON was empty/invalid, so local route_agent_ids() picked specialists."
                    if used_fallback
                    else "Provider returned usable agent_ids JSON; no fallback needed."
                ),
            },
            messages=manager_messages,
        )
        return _run_specialists(
            routed_agent_ids,
            request,
            provider=self.provider,
            trace=trace,
        )


def _run_specialists(
    routed_agent_ids: Sequence[str],
    request: SupervisorRequest,
    *,
    provider: ModelProvider | None = None,
    trace: TurnTrace | None = None,
) -> SupervisorResponse:
    agent_results: list[AgentRunResult] = []
    for agent_id in routed_agent_ids:
        handoff_request = _handoff_request(request, agent_id, agent_results)
        if is_specialist_agent_id(agent_id):
            agent = request.agent_catalog.get(agent_id)
            if agent is not None:
                agent_results.append(
                    _run_custom_agent(
                        agent,
                        handoff_request,
                        agent_results,
                        provider=provider,
                        trace=trace,
                    )
                )
            else:
                agent_results.append(
                    AgentRunResult(
                        agent_id=agent_id,
                        content=f"{agent_id} is not available in the current agent catalog.",
                        handoff_request=handoff_request,
                    )
                )
        else:
            agent_results.append(
                AgentRunResult(
                    agent_id=agent_id,
                    content=f"{agent_id} selected for a later supervisor task.",
                    handoff_request=handoff_request,
                )
            )

    follow_ups = _run_supervisor_follow_ups(request, agent_results)
    if follow_ups and trace is not None:
        trace.add(
            "follow_ups",
            "Supervisor follow-up tools (summarize / chart)",
            follow_up_agent_ids=[result.agent_id for result in follow_ups],
            follow_up_tool_outputs=[
                {
                    "agent_id": result.agent_id,
                    "tool_outputs": list(result.tool_outputs),
                }
                for result in follow_ups
            ],
        )
    agent_results.extend(follow_ups)

    if provider is not None:
        content = _synthesize_final_answer(
            provider,
            request,
            agent_results,
            trace=trace,
        )
    else:
        content = _synthesize_agent_results(agent_results)

    if trace is not None:
        trace.meta["final_answer"] = content
        trace.meta["called_agent_ids"] = [result.agent_id for result in agent_results]

    return SupervisorResponse(
        content=content,
        agent_results=agent_results,
        artifacts=_artifacts_from_agent_results(agent_results),
        turn_trace=None if trace is None else trace.to_dict(),
    )


def _manager_messages(request: SupervisorRequest) -> tuple[ModelMessage, ...]:
    agents = "\n".join(
        (
            f"- {agent.id}: {agent.description}"
            for agent_id in allowed_specialist_ids(request)
            if (agent := request.agent_catalog.get(agent_id)) is not None
        )
    )
    conversation_context = "\n".join(
        f"{message.role}: {message.content}" for message in request.messages[-6:]
    )
    prompt = (
        "Choose which local specialist agents should help with the user's request.\n"
        "Return only JSON in this shape: {\"agent_ids\": [\"agent_id\"]}.\n"
        "Use only these available specialists:\n"
        f"{agents}\n\n"
        "Conversation context:\n"
        f"{conversation_context or '(none)'}\n\n"
        f"User request: {request.user_input}"
    )
    return (
        ModelMessage(
            role="system",
            content=(
                "You are the local group chat manager for an agent team. "
                "Select the smallest useful set of specialist agent ids."
            ),
            agent_name="supervisor",
        ),
        ModelMessage(role="user", content=prompt, agent_name="supervisor"),
    )


def _agent_ids_from_provider_decision(
    provider_content: str,
    request: SupervisorRequest,
) -> tuple[tuple[str, ...], bool]:
    allowed = set(allowed_specialist_ids(request))
    agent_ids = _parse_agent_ids(provider_content, allowed)
    routed_agent_ids = stable_specialist_order(
        tuple(agent_id for agent_id in agent_ids if agent_id in allowed)
    )
    if routed_agent_ids:
        return routed_agent_ids, False

    return route_agent_ids(request), True


def _parse_agent_ids(
    provider_content: str,
    allowed_agent_ids: set[str],
) -> tuple[str, ...]:
    try:
        parsed = json.loads(provider_content)
    except json.JSONDecodeError:
        return tuple(
            agent_id for agent_id in allowed_agent_ids if agent_id in provider_content
        )

    if not isinstance(parsed, Mapping):
        return ()
    agent_ids = parsed.get("agent_ids")
    if not isinstance(agent_ids, list):
        return ()
    return tuple(agent_id for agent_id in agent_ids if isinstance(agent_id, str))
