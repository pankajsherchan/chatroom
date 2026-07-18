"""Chat turn orchestration: run supervisor, then persist a completed turn."""

from __future__ import annotations

import time
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
import sqlite3
from typing import Any

from fastapi import HTTPException

from app.agent_registry import build_agent_catalog
from app.models.supervisor import GroupChatEvent, SupervisorRequest, SupervisorResponse
from app.observability import duration_ms, log_event
from app.providers import ModelMessage
from app.providers.factory import create_model_provider
from app.settings import Settings, effective_settings
from app.storage import (
    Conversation,
    Message,
    append_artifact,
    append_group_chat_event,
    append_message,
    list_messages,
    update_conversation_title,
)
from app.supervisor import ProviderSupervisor
from app.tool_registry import tool_connection_scope
from app.turn_report import write_turn_report


DEFAULT_CONVERSATION_TITLE = "New conversation"
AUTO_TITLE_MAX_LENGTH = 72


@dataclass(frozen=True)
class ChatTurnResult:
    """Completed turn payload ready for buffered response replay."""

    content: str
    request_id: str
    provider_id: str
    model_name: str | None
    selected_agent_ids: list[str]
    turn_report_path: str | None
    group_chat_events: tuple[GroupChatEvent, ...]
    artifacts: tuple[Mapping[str, Any], ...]


class ChatTurnService:
    """Run the supervisor before sequentially persisting a completed turn."""

    def run_turn(
        self,
        *,
        connection: sqlite3.Connection,
        conversation: Conversation,
        user_content: str,
        settings: Settings,
        request_id: str,
    ) -> ChatTurnResult:
        runtime_settings = effective_settings(settings)
        provider_id = runtime_settings.model_provider
        prior_messages = list_messages(connection, conversation.id)
        model_messages = [
            *_messages_to_model_messages(prior_messages),
            ModelMessage(role="user", content=user_content),
        ]

        title_should_update = (
            not prior_messages and conversation.title == DEFAULT_CONVERSATION_TITLE
        )
        next_title = (
            title_from_first_message(user_content) if title_should_update else None
        )

        with tool_connection_scope(connection):
            try:
                provider = create_model_provider(runtime_settings)
            except ValueError as error:
                raise HTTPException(status_code=400, detail=str(error)) from error

            model_name = provider_model_name(provider)
            supervisor_started_at = time.perf_counter()
            log_event(
                "supervisor_started",
                request_id=request_id,
                conversation_id=conversation.id,
                execution_mode="provider_supervisor",
                provider_id=provider_id,
                model_name=model_name,
                selected_agent_ids=conversation.selected_agent_ids,
            )
            try:
                supervisor_response = ProviderSupervisor(provider).run(
                    SupervisorRequest(
                        selected_agent_ids=conversation.selected_agent_ids,
                        messages=model_messages,
                        user_input=user_content,
                        agent_catalog=build_agent_catalog(
                            connection,
                            list(conversation.selected_agent_ids),
                        ),
                    )
                )
            except Exception as error:
                log_event(
                    "supervisor_failed",
                    request_id=request_id,
                    conversation_id=conversation.id,
                    execution_mode="provider_supervisor",
                    provider_id=provider_id,
                    model_name=model_name,
                    selected_agent_ids=conversation.selected_agent_ids,
                    status="error",
                    duration_ms=duration_ms(supervisor_started_at),
                    error=str(error),
                )
                raise HTTPException(
                    status_code=503,
                    detail=f"Model provider failed: {error}",
                ) from error

            report_path = _maybe_write_turn_report(
                supervisor_response,
                conversation_id=conversation.id,
                request_id=request_id,
                provider_id=provider_id,
                model_name=model_name,
                selected_agent_ids=list(conversation.selected_agent_ids),
                user_content=user_content,
                prior_message_count=len(prior_messages),
                title_updated=title_should_update,
            )

            log_event(
                "supervisor_finished",
                request_id=request_id,
                conversation_id=conversation.id,
                execution_mode="provider_supervisor",
                provider_id=provider_id,
                model_name=model_name,
                selected_agent_ids=conversation.selected_agent_ids,
                status="success",
                duration_ms=duration_ms(supervisor_started_at),
                specialist_count=len(supervisor_response.agent_results),
                turn_report_path=str(report_path) if report_path is not None else None,
            )

            persist_completed_turn(
                connection,
                conversation_id=conversation.id,
                user_content=user_content,
                assistant_content=supervisor_response.content,
                provider_id=provider_id,
                model_name=model_name,
                group_chat_events=supervisor_response.transcript_events,
                artifacts=supervisor_response.artifacts,
                next_title=next_title,
            )

            return ChatTurnResult(
                content=supervisor_response.content,
                request_id=request_id,
                provider_id=provider_id,
                model_name=model_name,
                selected_agent_ids=list(conversation.selected_agent_ids),
                turn_report_path=str(report_path) if report_path is not None else None,
                group_chat_events=supervisor_response.transcript_events,
                artifacts=tuple(supervisor_response.artifacts),
            )


def persist_completed_turn(
    connection: sqlite3.Connection,
    *,
    conversation_id: str,
    user_content: str,
    assistant_content: str,
    provider_id: str | None,
    model_name: str | None,
    group_chat_events: Iterable[GroupChatEvent],
    artifacts: Iterable[Mapping[str, object]],
    next_title: str | None = None,
) -> None:
    """Persist title, messages, artifacts, and inspect events for one turn."""

    if next_title is not None:
        update_conversation_title(
            connection,
            conversation_id,
            title=next_title,
        )

    append_message(
        connection,
        conversation_id=conversation_id,
        role="user",
        content=user_content,
    )
    assistant_message = append_message(
        connection,
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        agent_name="supervisor",
        provider_id=provider_id,
        model_name=model_name,
    )
    for artifact in artifacts:
        _persist_artifact(
            connection,
            conversation_id=conversation_id,
            message_id=assistant_message.id,
            artifact=artifact,
        )
    for event in group_chat_events:
        append_group_chat_event(
            connection,
            conversation_id=conversation_id,
            event_type=event.event_type,
            agent_id=event.agent_id,
            content=event.content,
            payload=dict(event.payload),
        )


def title_from_first_message(
    content: str,
    *,
    max_length: int = AUTO_TITLE_MAX_LENGTH,
) -> str:
    cleaned = " ".join(content.strip().split())
    if not cleaned:
        return DEFAULT_CONVERSATION_TITLE
    if len(cleaned) <= max_length:
        return cleaned

    truncated = cleaned[: max_length - 1].rstrip()
    if " " in truncated:
        truncated = truncated.rsplit(" ", 1)[0].rstrip()
    if not truncated:
        truncated = cleaned[: max_length - 1].rstrip()
    return f"{truncated}…"


def provider_model_name(provider: object) -> str | None:
    model = getattr(provider, "model", None)
    if isinstance(model, str):
        return model

    model_id = getattr(provider, "model_id", None)
    if isinstance(model_id, str):
        return model_id

    return None


def stream_text(text: str, chunk_size: int = 24) -> Iterable[str]:
    """Replay a completed answer as buffered text chunks (not live tokens)."""

    for start in range(0, len(text), chunk_size):
        yield text[start : start + chunk_size]


def _messages_to_model_messages(messages: list[Message]) -> list[ModelMessage]:
    return [
        ModelMessage(
            role=message.role,
            content=message.content,
            agent_name=message.agent_name,
        )
        for message in messages
    ]


def _persist_artifact(
    connection: sqlite3.Connection,
    *,
    conversation_id: str,
    message_id: str,
    artifact: Mapping[str, object],
) -> None:
    artifact_type = artifact.get("type")
    payload = artifact.get("spec")
    if artifact_type != "chart" or not isinstance(payload, dict):
        return

    title = payload.get("title")
    append_artifact(
        connection,
        conversation_id=conversation_id,
        message_id=message_id,
        artifact_type="chart",
        title=title if isinstance(title, str) and title else "Untitled chart",
        payload={
            "agent_id": artifact.get("agent_id"),
            "spec": payload,
        },
    )


def _maybe_write_turn_report(
    supervisor_response: SupervisorResponse,
    *,
    conversation_id: str,
    request_id: str,
    provider_id: str,
    model_name: str | None,
    selected_agent_ids: list[str],
    user_content: str,
    prior_message_count: int,
    title_updated: bool,
):
    report_path = None
    try:
        report_path = write_turn_report(
            supervisor_response.turn_trace,
            conversation_id=conversation_id,
            request_id=request_id,
            provider_id=provider_id,
            model_name=model_name,
            final_answer=supervisor_response.content,
            selected_agent_ids=selected_agent_ids,
            request_context={
                "ui_action": (
                    "User typed a message in the chat composer and pressed send."
                ),
                "http_method": "POST",
                "api_endpoint": (
                    f"/conversations/{conversation_id}/messages/stream"
                ),
                "request_body": {"content": user_content},
                "conversation_id": conversation_id,
                "request_id": request_id,
                "persisted_before_supervisor": {
                    "user_message_appended": False,
                    "prior_messages_before_this_turn": prior_message_count,
                    "title_updated_from_first_message": title_updated,
                },
                "runtime": {
                    "provider_id": provider_id,
                    "model_name": model_name,
                    "selected_agent_ids": list(selected_agent_ids),
                },
                "next_step": (
                    "Backend builds SupervisorRequest and runs ProviderSupervisor."
                ),
            },
        )
    except Exception as error:  # noqa: BLE001 - reports must not break chat
        log_event(
            "turn_report_failed",
            request_id=request_id,
            conversation_id=conversation_id,
            status="error",
            error=str(error),
        )
        return None

    if report_path is not None:
        print(f"[turn-report] {report_path}", flush=True)
        log_event(
            "turn_report_written",
            request_id=request_id,
            conversation_id=conversation_id,
            path=str(report_path),
        )
    return report_path
