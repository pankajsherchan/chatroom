import json
from collections.abc import Mapping, Sequence
from typing import Any

from app.providers.base import ModelMessage, ToolCall, ToolSpec


def to_chat_messages(messages: Sequence[ModelMessage]) -> list[dict[str, str]]:
    return [{"role": message.role, "content": message.content} for message in messages]


def to_openai_input(messages: Sequence[ModelMessage]) -> list[dict[str, str]]:
    return to_chat_messages(messages)


def to_ollama_input(messages: Sequence[ModelMessage]) -> list[dict[str, str]]:
    return to_chat_messages(messages)


def to_openai_tools(tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    """Convert provider-neutral tool specs to OpenAI Responses function tools."""

    return [_to_openai_tool(tool) for tool in tools]


def to_ollama_tools(tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    """Convert provider-neutral tool specs to Ollama function tools."""

    return [_to_ollama_tool(tool) for tool in tools]


def to_bedrock_tools(tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    """Convert provider-neutral tool specs to Bedrock Converse toolConfig tools."""

    return [_to_bedrock_tool(tool) for tool in tools]


def _to_openai_tool(tool: ToolSpec) -> dict[str, Any]:
    if _looks_like_openai_tool(tool):
        return dict(tool)

    name, description, parameters = _neutral_tool_fields(tool)
    return {
        "type": "function",
        "name": name,
        "description": description,
        "parameters": parameters,
    }


def _to_ollama_tool(tool: ToolSpec) -> dict[str, Any]:
    if _looks_like_ollama_tool(tool):
        return dict(tool)

    name, description, parameters = _neutral_tool_fields(tool)
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": parameters,
        },
    }


def _to_bedrock_tool(tool: ToolSpec) -> dict[str, Any]:
    if _looks_like_bedrock_tool(tool):
        return dict(tool)

    name, description, parameters = _neutral_tool_fields(tool)
    return {
        "toolSpec": {
            "name": name,
            "description": description,
            "inputSchema": {"json": parameters},
        }
    }


def _looks_like_openai_tool(tool: ToolSpec) -> bool:
    return tool.get("type") == "function" and isinstance(tool.get("name"), str)


def _looks_like_ollama_tool(tool: ToolSpec) -> bool:
    function = tool.get("function")
    return (
        tool.get("type") == "function"
        and isinstance(function, Mapping)
        and isinstance(function.get("name"), str)
    )


def _looks_like_bedrock_tool(tool: ToolSpec) -> bool:
    tool_spec = tool.get("toolSpec")
    return isinstance(tool_spec, Mapping) and isinstance(tool_spec.get("name"), str)


def _neutral_tool_fields(tool: ToolSpec) -> tuple[str, str, dict[str, Any]]:
    name = tool.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError("Tool spec requires a non-empty name.")

    description = tool.get("description", "")
    if not isinstance(description, str):
        description = ""

    parameters = tool.get("parameters", {})
    if not isinstance(parameters, Mapping):
        parameters = {}

    return name, description, dict(parameters)


def bedrock_request_kwargs(
    messages: Sequence[ModelMessage],
    tools: Sequence[ToolSpec],
) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "messages": _to_bedrock_messages(messages),
    }
    system = _to_bedrock_system(messages)
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["toolConfig"] = {"tools": to_bedrock_tools(tools)}
    return kwargs


def _to_bedrock_messages(messages: Sequence[ModelMessage]) -> list[dict[str, Any]]:
    bedrock_messages: list[dict[str, Any]] = []
    for message in messages:
        if message.role == "system":
            continue
        role = message.role if message.role in {"user", "assistant"} else "user"
        bedrock_messages.append(
            {
                "role": role,
                "content": [{"text": message.content}],
            }
        )
    return bedrock_messages


def _to_bedrock_system(messages: Sequence[ModelMessage]) -> list[dict[str, str]]:
    return [{"text": message.content} for message in messages if message.role == "system"]


def response_output_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str):
        return output_text

    output = getattr(response, "output", ())
    parts: list[str] = []
    for item in output:
        for content in getattr(item, "content", ()):
            text = getattr(content, "text", None)
            if isinstance(text, str):
                parts.append(text)
    return "".join(parts)


def stream_text_delta(event: Any) -> str:
    if getattr(event, "type", None) != "response.output_text.delta":
        return ""

    delta = getattr(event, "delta", "")
    if isinstance(delta, str):
        return delta
    return ""


def openai_tool_calls(response: Any) -> tuple[ToolCall, ...]:
    tool_calls: list[ToolCall] = []
    for item in getattr(response, "output", ()):
        if getattr(item, "type", None) != "function_call":
            continue

        name = getattr(item, "name", None)
        if not isinstance(name, str) or not name:
            continue

        tool_calls.append(
            ToolCall(
                name=name,
                arguments=_json_object(getattr(item, "arguments", {})),
            )
        )

    return tuple(tool_calls)


def chat_message_content(response: Any) -> str:
    message = _message_mapping(response)
    content = message.get("content", "")
    return content if isinstance(content, str) else ""


def ollama_tool_calls(response: Any) -> tuple[ToolCall, ...]:
    message = _message_mapping(response)
    raw_calls = message.get("tool_calls", ())
    if not isinstance(raw_calls, Sequence) or isinstance(raw_calls, (str, bytes)):
        return ()

    tool_calls: list[ToolCall] = []
    for raw_call in raw_calls:
        function = _tool_call_function(raw_call)
        if not function:
            continue

        name = function.get("name")
        if not isinstance(name, str) or not name:
            continue

        arguments = function.get("arguments", {})
        if not isinstance(arguments, Mapping):
            arguments = {}

        tool_calls.append(ToolCall(name=name, arguments=dict(arguments)))

    return tuple(tool_calls)


def bedrock_tool_calls(response: Mapping[str, Any]) -> tuple[ToolCall, ...]:
    content_blocks = (
        response.get("output", {})
        .get("message", {})
        .get("content", ())
    )
    if not isinstance(content_blocks, Sequence) or isinstance(
        content_blocks, (str, bytes)
    ):
        return ()

    tool_calls: list[ToolCall] = []
    for block in content_blocks:
        if not isinstance(block, Mapping):
            continue

        tool_use = block.get("toolUse")
        if not isinstance(tool_use, Mapping):
            continue

        name = tool_use.get("name")
        if not isinstance(name, str) or not name:
            continue

        arguments = tool_use.get("input", {})
        if not isinstance(arguments, Mapping):
            arguments = {}

        tool_calls.append(ToolCall(name=name, arguments=dict(arguments)))

    return tuple(tool_calls)


def _message_mapping(response: Any) -> Mapping[str, Any]:
    if isinstance(response, Mapping):
        message = response.get("message", {})
        return message if isinstance(message, Mapping) else {}

    message = getattr(response, "message", {})
    if isinstance(message, Mapping):
        return message

    content = getattr(message, "content", "")
    return {
        "content": content if isinstance(content, str) else "",
        "tool_calls": getattr(message, "tool_calls", ()),
    }


def _tool_call_function(raw_call: Any) -> Mapping[str, Any]:
    if isinstance(raw_call, Mapping):
        function = raw_call.get("function", {})
    else:
        function = getattr(raw_call, "function", {})

    if isinstance(function, Mapping):
        return function

    name = getattr(function, "name", None)
    arguments = getattr(function, "arguments", {})
    return {
        "name": name,
        "arguments": arguments,
    }


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        return dict(value)

    if isinstance(value, str) and value.strip():
        parsed = json.loads(value)
        if isinstance(parsed, Mapping):
            return dict(parsed)

    return {}


def bedrock_output_text(response: Mapping[str, Any]) -> str:
    content_blocks = (
        response.get("output", {})
        .get("message", {})
        .get("content", ())
    )
    parts = []
    for block in content_blocks:
        text = block.get("text") if isinstance(block, Mapping) else None
        if isinstance(text, str):
            parts.append(text)
    return "".join(parts)


def bedrock_stream_text_delta(event: Mapping[str, Any]) -> str:
    content_delta = event.get("contentBlockDelta", {})
    if not isinstance(content_delta, Mapping):
        return ""
    delta = content_delta.get("delta", {})
    if not isinstance(delta, Mapping):
        return ""
    text = delta.get("text", "")
    return text if isinstance(text, str) else ""
