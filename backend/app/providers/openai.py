from collections.abc import Iterable
from typing import Any, Sequence

from app.providers.base import ModelMessage, ModelResponse, ToolSpec
from app.providers.conversions import (
    openai_tool_calls,
    response_output_text,
    stream_text_delta,
    to_openai_input,
    to_openai_tools,
)


DEFAULT_OPENAI_MODEL = "gpt-5.4-mini"

class OpenAIProvider:
    """OpenAI Responses API adapter."""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = DEFAULT_OPENAI_MODEL,
        client: Any | None = None,
    ) -> None:
        if api_key.strip() == "":
            raise ValueError("OPENAI_API_KEY is required for OpenAIProvider.")

        self.model = model
        self._client = client or _create_openai_client(api_key)

    def generate(
        self,
        messages: Sequence[ModelMessage],
        *,
        tools: Sequence[ToolSpec] = (),
    ) -> ModelResponse:
        response = self._client.responses.create(**self._request_kwargs(messages, tools))
        return ModelResponse(
            content=response_output_text(response),
            tool_calls=openai_tool_calls(response),
        )

    def stream(
        self,
        messages: Sequence[ModelMessage],
        *,
        tools: Sequence[ToolSpec] = (),
    ) -> Iterable[str]:
        stream = self._client.responses.create(
            **self._request_kwargs(messages, tools),
            stream=True,
        )

        for event in stream:
            delta = stream_text_delta(event)
            if delta:
                yield delta

    def _request_kwargs(
        self,
        messages: Sequence[ModelMessage],
        tools: Sequence[ToolSpec],
    ) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "input": to_openai_input(messages),
        }
        if tools:
            kwargs["tools"] = to_openai_tools(tools)
        return kwargs


def _create_openai_client(api_key: str) -> Any:
    from openai import OpenAI

    return OpenAI(api_key=api_key)
