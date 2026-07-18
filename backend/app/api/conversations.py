"""Conversation API routes."""

from collections.abc import Iterable
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse

from app.agent_registry import resolve_agent
from app.database import get_database_connection
from app.models import (
    ConversationDetailResponse,
    ConversationResponse,
    CreateConversationRequest,
    ArtifactResponse,
    GroupChatEventResponse,
    MessageResponse,
    SendMessageRequest,
    UpdateConversationRequest,
)
from app.observability import (
    new_request_id,
    stream_with_request_logging,
)
from app.services.chat_turn import ChatTurnService, stream_text
from app.settings import Settings, get_settings
from app.storage import (
    Artifact,
    Conversation,
    GroupChatEventRecord,
    Message,
    create_conversation,
    delete_conversation,
    get_conversation,
    list_conversations,
    list_artifacts,
    list_group_chat_events,
    list_messages,
    update_conversation_title,
)
from app.connector_agents import list_connector_agent_ids


router = APIRouter()

SUPERVISOR_AGENT_ID = "supervisor"


@router.get("/conversations", response_model=list[ConversationResponse])
def conversations_list(
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
):
    return [
        _conversation_to_response(conversation)
        for conversation in list_conversations(connection)
    ]


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
)
def conversation(
    conversation_id: str,
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
):
    found = get_conversation(connection, conversation_id)
    if found is None:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation not found: {conversation_id}",
        )

    return _conversation_detail_to_response(
        found,
        list_messages(connection, conversation_id),
        list_group_chat_events(connection, conversation_id),
        list_artifacts(connection, conversation_id),
    )


@router.post("/conversations", response_model=ConversationResponse, status_code=201)
def conversations(
    request: CreateConversationRequest,
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
):
    normalized_agent_ids = _normalize_selected_agent_ids(request.selected_agent_ids)
    _validate_agent_ids(connection, normalized_agent_ids)
    conversation = create_conversation(
        connection,
        selected_agent_ids=normalized_agent_ids,
    )
    return _conversation_to_response(conversation)


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
)
def rename_conversation(
    conversation_id: str,
    request: UpdateConversationRequest,
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
):
    title = request.title.strip()
    if not title:
        raise HTTPException(
            status_code=400,
            detail="Conversation title cannot be empty.",
        )

    updated = update_conversation_title(
        connection,
        conversation_id,
        title=title,
    )
    if updated is None:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation not found: {conversation_id}",
        )

    return _conversation_to_response(updated)


@router.delete("/conversations/{conversation_id}", status_code=204)
def remove_conversation(
    conversation_id: str,
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
):
    deleted = delete_conversation(connection, conversation_id)
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation not found: {conversation_id}",
        )

    return Response(status_code=204)


@router.post(
    "/conversations/{conversation_id}/messages/stream",
)
def stream_message(
    conversation_id: str,
    request: SendMessageRequest,
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
    settings: Annotated[Settings, Depends(get_settings)],
):
    """Run a supervised turn, persist results, then replay buffered text chunks.

    The response is not live provider-token streaming. The supervisor completes
    first; this endpoint then returns the finished answer in small chunks.
    """

    found = get_conversation(connection, conversation_id)
    if found is None:
        raise HTTPException(
            status_code=404,
            detail=f"Conversation not found: {conversation_id}",
        )

    request_id = new_request_id()
    turn = ChatTurnService().run_turn(
        connection=connection,
        conversation=found,
        user_content=request.content,
        settings=settings,
        request_id=request_id,
    )
    return _buffered_text_response(
        stream_text(turn.content),
        request_id=turn.request_id,
        conversation_id=conversation_id,
        provider_id=turn.provider_id,
        model_name=turn.model_name,
        selected_agent_ids=turn.selected_agent_ids,
        turn_report_path=turn.turn_report_path,
    )


def _buffered_text_response(
    chunks: Iterable[str],
    *,
    request_id: str,
    conversation_id: str,
    provider_id: str | None,
    model_name: str | None,
    selected_agent_ids: list[str],
    turn_report_path: str | None = None,
) -> StreamingResponse:
    headers = {
        "X-Request-Id": request_id,
        "X-Stream-Mode": "buffered",
    }
    if turn_report_path:
        headers["X-Turn-Report-Path"] = turn_report_path
    return StreamingResponse(
        stream_with_request_logging(
            iter(chunks),
            request_id=request_id,
            conversation_id=conversation_id,
            execution_mode="provider_supervisor",
            provider_id=provider_id,
            model_name=model_name,
            selected_agent_ids=selected_agent_ids,
        ),
        media_type="text/plain",
        headers=headers,
    )


def _normalize_selected_agent_ids(agent_ids: list[str]) -> list[str]:
    """Persist the implicit supervisor, backend connector agents, and custom specialists."""

    connector_ids = list_connector_agent_ids(get_settings())
    specialist_ids = [
        agent_id
        for agent_id in dict.fromkeys(agent_ids)
        if agent_id != SUPERVISOR_AGENT_ID and agent_id not in connector_ids
    ]
    merged_specialists = [
        *connector_ids,
        *[agent_id for agent_id in specialist_ids if agent_id not in connector_ids],
    ]
    if not merged_specialists:
        return [SUPERVISOR_AGENT_ID]
    return [SUPERVISOR_AGENT_ID, *merged_specialists]


def _validate_agent_ids(
    connection: sqlite3.Connection,
    agent_ids: list[str],
) -> None:
    unknown_agent_ids = [
        agent_id
        for agent_id in agent_ids
        if resolve_agent(connection, agent_id) is None
    ]
    if unknown_agent_ids:
        unknown = ", ".join(unknown_agent_ids)
        raise HTTPException(
            status_code=400,
            detail=f"Unknown selected_agent_ids: {unknown}",
        )


def _conversation_to_response(conversation: Conversation) -> ConversationResponse:
    return ConversationResponse(
        id=conversation.id,
        title=conversation.title,
        selected_agent_ids=conversation.selected_agent_ids,
        created_at=conversation.created_at,
    )


def _conversation_detail_to_response(
    conversation: Conversation,
    messages: list[Message],
    group_chat_events: list[GroupChatEventRecord],
    artifacts: list[Artifact],
) -> ConversationDetailResponse:
    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        selected_agent_ids=conversation.selected_agent_ids,
        created_at=conversation.created_at,
        messages=[_message_to_response(message) for message in messages],
        group_chat_events=[
            _group_chat_event_to_response(event) for event in group_chat_events
        ],
        artifacts=[_artifact_to_response(artifact) for artifact in artifacts],
    )


def _message_to_response(message: Message) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        conversation_id=message.conversation_id,
        role=message.role,
        content=message.content,
        agent_name=message.agent_name,
        provider_id=message.provider_id,
        model_name=message.model_name,
        created_at=message.created_at,
    )


def _group_chat_event_to_response(
    event: GroupChatEventRecord,
) -> GroupChatEventResponse:
    return GroupChatEventResponse(
        id=event.id,
        conversation_id=event.conversation_id,
        event_type=event.event_type,
        agent_id=event.agent_id,
        content=event.content,
        payload=event.payload,
        created_at=event.created_at,
    )


def _artifact_to_response(artifact: Artifact) -> ArtifactResponse:
    return ArtifactResponse(
        id=artifact.id,
        conversation_id=artifact.conversation_id,
        message_id=artifact.message_id,
        artifact_type=artifact.artifact_type,
        title=artifact.title,
        payload=artifact.payload,
        created_at=artifact.created_at,
    )
