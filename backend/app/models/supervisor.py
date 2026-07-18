"""Supervisor orchestration models."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from typing import Literal

from app.agents import LocalAgent, SUPERVISOR_TEAM_AGENT_IDS, get_agent
from app.providers import ModelMessage

GroupChatEventType = Literal[
    "manager_started",
    "specialist_selected",
    "tool_called",
    "tool_finished",
    "specialist_answered",
    "final_answer",
]


@dataclass(frozen=True)
class SupervisorRequest:
    """Inputs needed to orchestrate one user turn."""

    selected_agent_ids: Sequence[str]
    messages: Sequence[ModelMessage]
    user_input: str
    agent_catalog: Mapping[str, LocalAgent] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "selected_agent_ids", tuple(self.selected_agent_ids))
        object.__setattr__(self, "messages", tuple(self.messages))
        if self.agent_catalog:
            object.__setattr__(self, "agent_catalog", dict(self.agent_catalog))
            return

        relevant_ids = set(self.selected_agent_ids)
        if not relevant_ids or "supervisor" in relevant_ids:
            relevant_ids.update(SUPERVISOR_TEAM_AGENT_IDS)

        catalog = {
            agent_id: agent
            for agent_id in relevant_ids
            if (agent := get_agent(agent_id)) is not None
        }
        object.__setattr__(self, "agent_catalog", catalog)


@dataclass(frozen=True)
class AgentHandoffRequest:
    """Delegation request from the supervisor to one specialist agent."""

    original_user_input: str
    context: Sequence[ModelMessage]
    target_agent_id: str
    specific_request: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "context", tuple(self.context))


@dataclass(frozen=True)
class AgentRunResult:
    """Output produced by one specialist agent during orchestration."""

    agent_id: str
    content: str
    tool_outputs: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    handoff_request: AgentHandoffRequest | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "tool_outputs", tuple(self.tool_outputs))


@dataclass(frozen=True)
class GroupChatEvent:
    """Inspectable event produced during one supervised group-chat turn."""

    event_type: GroupChatEventType
    content: str
    agent_id: str | None = None
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SupervisorResponse:
    """Final synthesized answer from a supervisor turn."""

    content: str
    agent_results: Sequence[AgentRunResult] = field(default_factory=tuple)
    artifacts: Sequence[Mapping[str, Any]] = field(default_factory=tuple)
    turn_trace: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "agent_results", tuple(self.agent_results))
        object.__setattr__(self, "artifacts", tuple(self.artifacts))
        if self.turn_trace is not None:
            object.__setattr__(self, "turn_trace", dict(self.turn_trace))

    @property
    def called_agent_ids(self) -> tuple[str, ...]:
        """Return the specialist agents that contributed to the response."""

        return tuple(result.agent_id for result in self.agent_results)

    @property
    def transcript_events(self) -> tuple[GroupChatEvent, ...]:
        """Return manager, specialist, tool, and final-answer events."""

        events: list[GroupChatEvent] = [
            GroupChatEvent(
                event_type="manager_started",
                content="Supervisor started a local group-chat turn.",
                payload={"called_agent_ids": list(self.called_agent_ids)},
            )
        ]

        for result in self.agent_results:
            handoff = result.handoff_request
            events.append(
                GroupChatEvent(
                    event_type="specialist_selected",
                    agent_id=result.agent_id,
                    content=(
                        handoff.specific_request
                        if handoff is not None
                        else f"Selected {result.agent_id}."
                    ),
                    payload={
                        "original_user_input": (
                            handoff.original_user_input if handoff is not None else None
                        ),
                        "target_agent_id": result.agent_id,
                    },
                )
            )
            for tool_output in result.tool_outputs:
                tool_name = str(tool_output.get("tool_name", "unknown_tool"))
                events.append(
                    GroupChatEvent(
                        event_type="tool_called",
                        agent_id=result.agent_id,
                        content=f"{result.agent_id} called {tool_name}.",
                        payload={
                            "tool_name": tool_name,
                            "arguments": tool_output.get("arguments", {}),
                        },
                    )
                )
                events.append(
                    GroupChatEvent(
                        event_type="tool_finished",
                        agent_id=result.agent_id,
                        content=f"{tool_name} finished for {result.agent_id}.",
                        payload={
                            "tool_name": tool_name,
                            "output": tool_output.get("output"),
                        },
                    )
                )
            events.append(
                GroupChatEvent(
                    event_type="specialist_answered",
                    agent_id=result.agent_id,
                    content=result.content,
                )
            )

        events.append(
            GroupChatEvent(
                event_type="final_answer",
                content=self.content,
                payload={"artifact_count": len(self.artifacts)},
            )
        )
        return tuple(events)
