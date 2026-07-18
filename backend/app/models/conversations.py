"""Conversation API models."""

from typing import Any
from pydantic import BaseModel, Field


class CreateConversationRequest(BaseModel):
    """Payload for starting a selected-agent conversation."""

    selected_agent_ids: list[str] = Field(default_factory=list)


class UpdateConversationRequest(BaseModel):
    """Payload for renaming a saved conversation."""

    title: str = Field(..., min_length=1, max_length=200)


class ConversationResponse(BaseModel):
    """Conversation metadata returned by the API."""

    id: str
    title: str
    selected_agent_ids: list[str]
    created_at: str


class MessageResponse(BaseModel):
    """Message metadata and content returned by the API."""

    id: str
    conversation_id: str
    role: str
    content: str
    agent_name: str | None
    provider_id: str | None
    model_name: str | None
    created_at: str


class GroupChatEventResponse(BaseModel):
    """Persisted group-chat transcript event returned by the API."""

    id: str
    conversation_id: str
    event_type: str
    agent_id: str | None
    content: str
    payload: dict[str, Any]
    created_at: str


class ArtifactResponse(BaseModel):
    """Persisted generated artifact returned by the API."""

    id: str
    conversation_id: str
    message_id: str | None
    artifact_type: str
    title: str
    payload: dict[str, Any]
    created_at: str


class ConversationDetailResponse(ConversationResponse):
    """Conversation metadata plus ordered messages and inspect events."""

    messages: list[MessageResponse]
    group_chat_events: list[GroupChatEventResponse]
    artifacts: list[ArtifactResponse]


class SendMessageRequest(BaseModel):
    """Payload for sending a user message into a conversation."""

    content: str = Field(..., min_length=1)
