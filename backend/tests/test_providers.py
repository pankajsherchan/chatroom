from collections.abc import Iterable, Sequence
from types import SimpleNamespace

from app.providers import bedrock as bedrock_module
from app.providers import (
    BedrockProvider,
    DEFAULT_OPENAI_MODEL,
    ModelMessage,
    ModelProvider,
    ModelResponse,
    OpenAIProvider,
    OllamaProvider,
    ToolCall,
    ToolSpec,
    create_model_provider,
)
from app.settings import Settings


class EchoProvider:
    def generate(
        self,
        messages: Sequence[ModelMessage],
        *,
        tools: Sequence[ToolSpec] = (),
    ) -> ModelResponse:
        return ModelResponse(content=messages[-1].content, tool_calls=())

    def stream(
        self,
        messages: Sequence[ModelMessage],
        *,
        tools: Sequence[ToolSpec] = (),
    ) -> Iterable[str]:
        return iter(messages[-1].content.split())


class FakeResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream") is True:
            return iter(
                [
                    SimpleNamespace(type="response.created", delta=""),
                    SimpleNamespace(type="response.output_text.delta", delta="hello "),
                    SimpleNamespace(type="response.output_text.delta", delta="world"),
                ]
            )
        return SimpleNamespace(output_text="hello world")


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.responses = FakeResponses()


class FakeOpenAIToolResponses:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            output_text="",
            output=[
                SimpleNamespace(
                    type="function_call",
                    name="query_snowflake",
                    arguments='{"filters":{"region":"West"}}',
                )
            ],
        )


class FakeOpenAIToolClient:
    def __init__(self) -> None:
        self.responses = FakeOpenAIToolResponses()


class FakeOllamaClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream") is True:
            return iter(
                [
                    {"message": {"content": "hello "}},
                    {"message": {"content": "world"}},
                    {"done": True},
                ]
            )
        return {"message": {"content": "hello world"}}


class FakeOllamaToolClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "message": {
                "content": "",
                "tool_calls": [
                    {
                        "function": {
                            "name": "query_snowflake",
                            "arguments": {"filters": {"region": "West"}},
                        }
                    }
                ],
            }
        }


class FakeOllamaObjectClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("stream") is True:
            return iter(
                [
                    SimpleNamespace(message=SimpleNamespace(content="hello ")),
                    SimpleNamespace(message=SimpleNamespace(content="world")),
                ]
            )
        return SimpleNamespace(message=SimpleNamespace(content="hello world"))


class FakeOllamaObjectToolClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def chat(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            message=SimpleNamespace(
                content="",
                tool_calls=[
                    SimpleNamespace(
                        function=SimpleNamespace(
                            name="query_snowflake",
                            arguments={"filters": {"region": "West"}},
                        )
                    )
                ],
            )
        )


class FakeBedrockClient:
    def __init__(self) -> None:
        self.converse_calls: list[dict[str, object]] = []
        self.converse_stream_calls: list[dict[str, object]] = []

    def converse(self, **kwargs):
        self.converse_calls.append(kwargs)
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {"text": "hello "},
                        {"text": "world"},
                    ],
                }
            }
        }

    def converse_stream(self, **kwargs):
        self.converse_stream_calls.append(kwargs)
        return {
            "stream": iter(
                [
                    {"messageStart": {"role": "assistant"}},
                    {"contentBlockDelta": {"delta": {"text": "hello "}}},
                    {"contentBlockDelta": {"delta": {"text": "world"}}},
                    {"messageStop": {"stopReason": "end_turn"}},
                ]
            )
        }


class FakeBedrockToolClient:
    def __init__(self) -> None:
        self.converse_calls: list[dict[str, object]] = []

    def converse(self, **kwargs):
        self.converse_calls.append(kwargs)
        return {
            "output": {
                "message": {
                    "role": "assistant",
                    "content": [
                        {
                            "toolUse": {
                                "name": "query_snowflake",
                                "input": {"filters": {"region": "West"}},
                            }
                        }
                    ],
                }
            }
        }


def test_model_provider_protocol_supports_generate_and_stream():
    provider: ModelProvider = EchoProvider()

    response = provider.generate([ModelMessage(role="user", content="hello world")])
    chunks = list(provider.stream([ModelMessage(role="user", content="hello world")]))

    assert response == ModelResponse(content="hello world")
    assert chunks == ["hello", "world"]


def test_model_response_can_include_tool_calls():
    response = ModelResponse(
        content="",
        tool_calls=(ToolCall(name="query_snowflake", arguments={"sql": "SELECT 1"}),),
    )

    assert response.tool_calls[0].name == "query_snowflake"
    assert response.tool_calls[0].arguments == {"sql": "SELECT 1"}


def test_neutral_tool_specs_convert_to_provider_shapes():
    from app.providers.conversions import (
        to_bedrock_tools,
        to_ollama_tools,
        to_openai_tools,
    )

    neutral = {
        "name": "query_snowflake",
        "description": "Run a read-only SELECT.",
        "parameters": {
            "type": "object",
            "properties": {"sql": {"type": "string"}},
            "required": ["sql"],
        },
    }

    assert to_openai_tools([neutral]) == [
        {
            "type": "function",
            "name": "query_snowflake",
            "description": "Run a read-only SELECT.",
            "parameters": neutral["parameters"],
        }
    ]
    assert to_ollama_tools([neutral]) == [
        {
            "type": "function",
            "function": {
                "name": "query_snowflake",
                "description": "Run a read-only SELECT.",
                "parameters": neutral["parameters"],
            },
        }
    ]
    assert to_bedrock_tools([neutral]) == [
        {
            "toolSpec": {
                "name": "query_snowflake",
                "description": "Run a read-only SELECT.",
                "inputSchema": {"json": neutral["parameters"]},
            }
        }
    ]


def test_openai_provider_accepts_neutral_tool_specs():
    client = FakeOpenAIClient()
    provider = OpenAIProvider(api_key="test-key", model="test-model", client=client)

    provider.generate(
        [ModelMessage(role="user", content="Use the sales tool.")],
        tools=(
            {
                "name": "query_snowflake",
                "description": "Run a read-only SELECT.",
                "parameters": {
                    "type": "object",
                    "properties": {"sql": {"type": "string"}},
                    "required": ["sql"],
                },
            },
        ),
    )

    assert client.responses.calls[0]["tools"] == [
        {
            "type": "function",
            "name": "query_snowflake",
            "description": "Run a read-only SELECT.",
            "parameters": {
                "type": "object",
                "properties": {"sql": {"type": "string"}},
                "required": ["sql"],
            },
        }
    ]


def test_ollama_provider_accepts_neutral_tool_specs():
    client = FakeOllamaClient()
    provider = OllamaProvider(
        base_url="http://localhost:11434",
        model="llama3.2",
        client=client,
    )

    provider.generate(
        [ModelMessage(role="user", content="Use the sales tool.")],
        tools=(
            {
                "name": "query_snowflake",
                "description": "Run a read-only SELECT.",
                "parameters": {
                    "type": "object",
                    "properties": {"sql": {"type": "string"}},
                    "required": ["sql"],
                },
            },
        ),
    )

    assert client.calls[0]["tools"] == [
        {
            "type": "function",
            "function": {
                "name": "query_snowflake",
                "description": "Run a read-only SELECT.",
                "parameters": {
                    "type": "object",
                    "properties": {"sql": {"type": "string"}},
                    "required": ["sql"],
                },
            },
        }
    ]


def test_bedrock_provider_accepts_neutral_tool_specs():
    client = FakeBedrockClient()
    provider = BedrockProvider(
        model_id="anthropic.claude-test",
        region="us-west-2",
        client=client,
    )

    provider.generate(
        [ModelMessage(role="user", content="Use the sales tool.")],
        tools=(
            {
                "name": "query_snowflake",
                "description": "Run a read-only SELECT.",
                "parameters": {
                    "type": "object",
                    "properties": {"sql": {"type": "string"}},
                    "required": ["sql"],
                },
            },
        ),
    )

    assert client.converse_calls[0]["toolConfig"]["tools"] == [
        {
            "toolSpec": {
                "name": "query_snowflake",
                "description": "Run a read-only SELECT.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {"sql": {"type": "string"}},
                        "required": ["sql"],
                    }
                },
            }
        }
    ]


def test_create_model_provider_returns_ollama_for_default_settings():
    settings = Settings.from_env({"OLLAMA_MODEL": "llama3.2"})

    provider = create_model_provider(settings)

    assert isinstance(provider, OllamaProvider)


def test_create_model_provider_rejects_unsupported_provider():
    try:
        Settings.from_env({"MODEL_PROVIDER": "mock"})
    except ValueError as error:
        assert "Unsupported MODEL_PROVIDER" in str(error)
    else:
        raise AssertionError("Expected Settings.from_env to reject MODEL_PROVIDER=mock")


def test_openai_provider_generates_response_with_responses_api_client():
    client = FakeOpenAIClient()
    provider = OpenAIProvider(api_key="test-key", model="test-model", client=client)

    response = provider.generate(
        [
            ModelMessage(role="system", content="Be concise."),
            ModelMessage(role="user", content="Say hello."),
        ],
        tools=({"type": "function", "name": "query_snowflake"},),
    )

    assert response == ModelResponse(content="hello world")
    assert client.responses.calls == [
        {
            "model": "test-model",
            "input": [
                {"role": "system", "content": "Be concise."},
                {"role": "user", "content": "Say hello."},
            ],
            "tools": [{"type": "function", "name": "query_snowflake"}],
        }
    ]


def test_openai_provider_normalizes_tool_calls():
    client = FakeOpenAIToolClient()
    provider = OpenAIProvider(api_key="test-key", model="test-model", client=client)

    response = provider.generate(
        [ModelMessage(role="user", content="Use the sales tool.")],
        tools=({"type": "function", "name": "query_snowflake"},),
    )

    assert response == ModelResponse(
        content="",
        tool_calls=(
            ToolCall(
                name="query_snowflake",
                arguments={"filters": {"region": "West"}},
            ),
        ),
    )
    assert client.responses.calls == [
        {
            "model": "test-model",
            "input": [{"role": "user", "content": "Use the sales tool."}],
            "tools": [{"type": "function", "name": "query_snowflake"}],
        }
    ]


def test_openai_provider_streams_text_deltas():
    client = FakeOpenAIClient()
    provider = OpenAIProvider(api_key="test-key", model="test-model", client=client)

    chunks = list(provider.stream([ModelMessage(role="user", content="Say hello.")]))

    assert chunks == ["hello ", "world"]
    assert client.responses.calls == [
        {
            "model": "test-model",
            "input": [{"role": "user", "content": "Say hello."}],
            "stream": True,
        }
    ]


def test_create_model_provider_returns_openai_provider_when_configured():
    settings = Settings.from_env(
        {
            "MODEL_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key",
            "OPENAI_MODEL": "test-model",
        }
    )

    provider = create_model_provider(settings)

    assert isinstance(provider, OpenAIProvider)
    assert provider.model == "test-model"


def test_create_model_provider_uses_default_openai_model():
    settings = Settings.from_env(
        {
            "MODEL_PROVIDER": "openai",
            "OPENAI_API_KEY": "test-key",
        }
    )

    provider = create_model_provider(settings)

    assert isinstance(provider, OpenAIProvider)
    assert provider.model == DEFAULT_OPENAI_MODEL


def test_create_model_provider_requires_openai_api_key():
    settings = Settings.from_env({"MODEL_PROVIDER": "openai"})

    try:
        create_model_provider(settings)
    except ValueError as error:
        assert "OPENAI_API_KEY is required" in str(error)
    else:
        raise AssertionError("Expected openai provider to require an API key")


def test_ollama_provider_generates_response_with_chat_client():
    client = FakeOllamaClient()
    provider = OllamaProvider(
        base_url="http://localhost:11434/",
        model="llama3.2",
        client=client,
    )

    response = provider.generate(
        [ModelMessage(role="user", content="Say hello.")],
        tools=({"type": "function", "function": {"name": "query_snowflake"}},),
    )

    assert provider.base_url == "http://localhost:11434"
    assert response == ModelResponse(content="hello world")
    assert client.calls == [
        {
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "Say hello."}],
            "tools": [{"type": "function", "function": {"name": "query_snowflake"}}],
            "stream": False,
        }
    ]


def test_ollama_provider_normalizes_tool_calls():
    client = FakeOllamaToolClient()
    provider = OllamaProvider(
        base_url="http://localhost:11434",
        model="llama3.2",
        client=client,
    )

    response = provider.generate(
        [ModelMessage(role="user", content="Use the sales tool.")],
        tools=(
            {
                "type": "function",
                "function": {"name": "query_snowflake"},
            },
        ),
    )

    assert response == ModelResponse(
        content="",
        tool_calls=(
            ToolCall(
                name="query_snowflake",
                arguments={"filters": {"region": "West"}},
            ),
        ),
    )
    assert client.calls == [
        {
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "Use the sales tool."}],
            "tools": [
                {
                    "type": "function",
                    "function": {"name": "query_snowflake"},
                }
            ],
            "stream": False,
        }
    ]


def test_ollama_provider_handles_object_response_content():
    client = FakeOllamaObjectClient()
    provider = OllamaProvider(
        base_url="http://localhost:11434",
        model="llama3.2",
        client=client,
    )

    response = provider.generate([ModelMessage(role="user", content="Say hello.")])
    chunks = list(provider.stream([ModelMessage(role="user", content="Say hello.")]))

    assert response == ModelResponse(content="hello world")
    assert chunks == ["hello ", "world"]


def test_ollama_provider_handles_object_response_tool_calls():
    client = FakeOllamaObjectToolClient()
    provider = OllamaProvider(
        base_url="http://localhost:11434",
        model="llama3.2",
        client=client,
    )

    response = provider.generate(
        [ModelMessage(role="user", content="Use the sales tool.")],
        tools=(
            {
                "type": "function",
                "function": {"name": "query_snowflake"},
            },
        ),
    )

    assert response == ModelResponse(
        content="",
        tool_calls=(
            ToolCall(
                name="query_snowflake",
                arguments={"filters": {"region": "West"}},
            ),
        ),
    )


def test_ollama_provider_streams_message_content_chunks():
    client = FakeOllamaClient()
    provider = OllamaProvider(
        base_url="http://localhost:11434",
        model="llama3.2",
        client=client,
    )

    chunks = list(provider.stream([ModelMessage(role="user", content="Say hello.")]))

    assert chunks == ["hello ", "world"]
    assert client.calls == [
        {
            "model": "llama3.2",
            "messages": [{"role": "user", "content": "Say hello."}],
            "tools": None,
            "stream": True,
        }
    ]


def test_create_model_provider_returns_ollama_provider_when_configured():
    settings = Settings.from_env(
        {
            "MODEL_PROVIDER": "ollama",
            "OLLAMA_BASE_URL": "http://localhost:11434/",
            "OLLAMA_MODEL": "llama3.2",
        }
    )

    provider = create_model_provider(settings)

    assert isinstance(provider, OllamaProvider)
    assert provider.base_url == "http://localhost:11434"
    assert provider.model == "llama3.2"


def test_create_model_provider_requires_ollama_model():
    settings = Settings.from_env({"MODEL_PROVIDER": "ollama"})

    try:
        create_model_provider(settings)
    except ValueError as error:
        assert "OLLAMA_MODEL is required" in str(error)
    else:
        raise AssertionError("Expected ollama provider to require a model")


def test_bedrock_provider_generates_response_with_converse_client():
    client = FakeBedrockClient()
    provider = BedrockProvider(
        model_id="anthropic.claude-test",
        region="us-west-2",
        aws_profile="test-profile",
        client=client,
    )

    response = provider.generate(
        [
            ModelMessage(role="system", content="Be concise."),
            ModelMessage(role="user", content="Say hello."),
        ],
        tools=({"toolSpec": {"name": "query_snowflake"}},),
    )

    assert provider.model_id == "anthropic.claude-test"
    assert provider.region == "us-west-2"
    assert provider.aws_profile == "test-profile"
    assert response == ModelResponse(content="hello world")
    assert client.converse_calls == [
        {
            "modelId": "anthropic.claude-test",
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": "Say hello."}],
                }
            ],
            "system": [{"text": "Be concise."}],
            "toolConfig": {"tools": [{"toolSpec": {"name": "query_snowflake"}}]},
        }
    ]


def test_bedrock_provider_normalizes_tool_calls():
    client = FakeBedrockToolClient()
    provider = BedrockProvider(
        model_id="anthropic.claude-test",
        region="us-west-2",
        client=client,
    )

    response = provider.generate(
        [ModelMessage(role="user", content="Use the sales tool.")],
        tools=({"toolSpec": {"name": "query_snowflake"}},),
    )

    assert response == ModelResponse(
        content="",
        tool_calls=(
            ToolCall(
                name="query_snowflake",
                arguments={"filters": {"region": "West"}},
            ),
        ),
    )
    assert client.converse_calls == [
        {
            "modelId": "anthropic.claude-test",
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": "Use the sales tool."}],
                }
            ],
            "toolConfig": {"tools": [{"toolSpec": {"name": "query_snowflake"}}]},
        }
    ]


def test_bedrock_provider_streams_text_deltas():
    client = FakeBedrockClient()
    provider = BedrockProvider(
        model_id="anthropic.claude-test",
        region="us-west-2",
        client=client,
    )

    chunks = list(provider.stream([ModelMessage(role="user", content="Say hello.")]))

    assert chunks == ["hello ", "world"]
    assert client.converse_stream_calls == [
        {
            "modelId": "anthropic.claude-test",
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": "Say hello."}],
                }
            ],
        }
    ]


def test_create_model_provider_returns_bedrock_provider_when_configured(monkeypatch):
    monkeypatch.setattr(
        bedrock_module,
        "_create_bedrock_client",
        lambda region, aws_profile: FakeBedrockClient(),
    )
    settings = Settings.from_env(
        {
            "MODEL_PROVIDER": "bedrock",
            "AWS_PROFILE": "test-profile",
            "AWS_REGION": "us-west-2",
            "BEDROCK_MODEL_ID": "anthropic.claude-test",
        }
    )

    provider = create_model_provider(settings)

    assert isinstance(provider, BedrockProvider)
    assert provider.model_id == "anthropic.claude-test"
    assert provider.region == "us-west-2"
    assert provider.aws_profile == "test-profile"


def test_create_model_provider_requires_bedrock_model_id():
    settings = Settings.from_env({"MODEL_PROVIDER": "bedrock"})

    try:
        create_model_provider(settings)
    except ValueError as error:
        assert "BEDROCK_MODEL_ID is required" in str(error)
    else:
        raise AssertionError("Expected bedrock provider to require a model id")
