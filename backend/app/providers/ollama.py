
from collections.abc import Iterable
from typing import Any, Sequence

from app.providers.base import ModelMessage, ModelResponse, ToolSpec
from app.providers.conversions import (
    chat_message_content,
    ollama_tool_calls,
    to_ollama_input,
    to_ollama_tools,
)


class OllamaProvider:
    """Ollama chat API adapter."""

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        client: Any | None = None,
    ) -> None:
        if model.strip() == "":
            raise ValueError("OLLAMA_MODEL is required for OllamaProvider.")

        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = client or _create_ollama_client(self.base_url)

    def generate(
        self,
        messages: Sequence[ModelMessage],
        *,
        tools: Sequence[ToolSpec] = (),
    ) -> ModelResponse:
        response = self._client.chat(
            model=self.model,
            messages=to_ollama_input(messages),
            tools=to_ollama_tools(tools) if tools else None,
            stream=False,
        )
        return ModelResponse(
            content=chat_message_content(response),
            tool_calls=ollama_tool_calls(response),
        )

    def stream(
        self,
        messages: Sequence[ModelMessage],
        *,
        tools: Sequence[ToolSpec] = (),
    ) -> Iterable[str]:
        stream = self._client.chat(
            model=self.model,
            messages=to_ollama_input(messages),
            tools=to_ollama_tools(tools) if tools else None,
            stream=True,
        )
        for chunk in stream:
            content = chat_message_content(chunk)
            if content:
                yield content




def _create_ollama_client(base_url: str) -> Any:
    from ollama import Client

    return Client(host=base_url)
