from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol, Sequence


ToolSpec = Mapping[str, Any]

@dataclass(frozen=True)
class ModelMessage:
    """A provider-neutral chat message."""

    role: str
    content: str
    agent_name: str | None = None


@dataclass(frozen=True)
class ToolCall:
    """A provider-neutral request to run a local tool."""

    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelResponse:
    """A full response returned by a model provider."""

    content: str
    tool_calls: Sequence[ToolCall] = ()


class ModelProvider(Protocol):
    """Common interface implemented by every model runtime adapter."""

    def generate(
        self,
        messages: Sequence[ModelMessage],
        *,
        tools: Sequence[ToolSpec] = (),
    ) -> ModelResponse:
        """Return one complete model response."""
        ...

    def stream(
        self,
        messages: Sequence[ModelMessage],
        *,
        tools: Sequence[ToolSpec] = (),
    ) -> Iterable[str]:
        """Yield response text chunks as they become available."""
        ...
