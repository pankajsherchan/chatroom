"""Tool API models."""

from typing import Any

from pydantic import BaseModel


class ToolExampleResponse(BaseModel):
    description: str
    arguments: dict[str, Any]


class ToolResponse(BaseModel):
    name: str
    description: str
    parameter_schema: dict[str, Any]
    examples: list[ToolExampleResponse]


class ToolsResponse(BaseModel):
    tools: list[ToolResponse]
