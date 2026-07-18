
from typing import Any, Iterable, Sequence

from app.providers.base import ModelMessage, ModelResponse, ToolSpec
from app.providers.conversions import (
    bedrock_output_text,
    bedrock_request_kwargs,
    bedrock_stream_text_delta,
    bedrock_tool_calls,
)


class BedrockProvider:
    """Amazon Bedrock Converse API adapter."""

    def __init__(
        self,
        *,
        model_id: str,
        region: str,
        aws_profile: str | None = None,
        client: Any | None = None,
    ) -> None:
        if model_id.strip() == "":
            raise ValueError("BEDROCK_MODEL_ID is required for BedrockProvider.")

        self.model_id = model_id
        self.region = region
        self.aws_profile = aws_profile
        self._client = client or _create_bedrock_client(region, aws_profile)

    def generate(
        self,
        messages: Sequence[ModelMessage],
        *,
        tools: Sequence[ToolSpec] = (),
    ) -> ModelResponse:
        response = self._client.converse(
            modelId=self.model_id,
            **bedrock_request_kwargs(messages, tools),
        )
        return ModelResponse(
            content=bedrock_output_text(response),
            tool_calls=bedrock_tool_calls(response),
        )

    def stream(
        self,
        messages: Sequence[ModelMessage],
        *,
        tools: Sequence[ToolSpec] = (),
    ) -> Iterable[str]:
        response = self._client.converse_stream(
            modelId=self.model_id,
            **bedrock_request_kwargs(messages, tools),
        )

        for event in response.get("stream", ()):
            delta = bedrock_stream_text_delta(event)
            if delta:
                yield delta


def _create_bedrock_client(region: str, aws_profile: str | None) -> Any:
    import boto3

    session = boto3.Session(profile_name=aws_profile, region_name=region)
    return session.client("bedrock-runtime")
