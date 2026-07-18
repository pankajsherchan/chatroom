"""Custom agent API models."""

from typing import Literal

from pydantic import BaseModel, Field

CustomAgentSource = Literal["builtin", "custom"]


class CustomAgentResponse(BaseModel):
    """Custom agent metadata returned by the API."""

    id: str
    name: str
    description: str
    system_prompt: str
    tools: list[str]
    source: CustomAgentSource = "custom"
    created_at: str
    updated_at: str


class CreateCustomAgentRequest(BaseModel):
    """Payload for creating a local custom agent."""

    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=1, max_length=500)
    system_prompt: str = Field(..., min_length=1, max_length=4000)
    tools: list[str] = Field(default_factory=list)


class UpdateCustomAgentRequest(BaseModel):
    """Payload for updating a local custom agent."""

    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=1, max_length=500)
    system_prompt: str = Field(..., min_length=1, max_length=4000)
    tools: list[str] = Field(default_factory=list)
