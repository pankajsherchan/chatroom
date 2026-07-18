from app.storage import (
    ToolTrace,
    append_tool_trace,
    create_conversation,
    list_tool_traces,
)


def test_append_tool_trace_returns_metadata(storage_connection):
    conversation = create_conversation(
        storage_connection,
        selected_agent_ids=["supervisor"],
    )

    trace = append_tool_trace(
        storage_connection,
        conversation_id=conversation.id,
        tool_name="query_snowflake",
        arguments={"filters": {"region": "West"}},
        output={"row_count": 6},
        error=None,
        status="success",
        provider_id="ollama",
        duration_ms=12,
    )

    assert isinstance(trace, ToolTrace)
    assert trace.id
    assert trace.conversation_id == conversation.id
    assert trace.tool_name == "query_snowflake"
    assert trace.arguments == {"filters": {"region": "West"}}
    assert trace.output == {"row_count": 6}
    assert trace.error is None
    assert trace.status == "success"
    assert trace.provider_id == "ollama"
    assert trace.duration_ms == 12
    assert trace.created_at


def test_list_tool_traces_returns_conversation_traces_in_insert_order(
    storage_connection,
):
    conversation = create_conversation(
        storage_connection,
        selected_agent_ids=["supervisor"],
    )
    other_conversation = create_conversation(
        storage_connection,
        selected_agent_ids=["summarizer"],
    )

    first = append_tool_trace(
        storage_connection,
        conversation_id=conversation.id,
        tool_name="query_snowflake",
        arguments={"filters": {"region": "West"}},
        output={"row_count": 6},
        error=None,
        status="success",
        provider_id="ollama",
        duration_ms=12,
    )
    second = append_tool_trace(
        storage_connection,
        conversation_id=conversation.id,
        tool_name="unknown_tool",
        arguments={},
        output=None,
        error="Unknown tool: unknown_tool",
        status="error",
        provider_id="ollama",
        duration_ms=0,
    )
    append_tool_trace(
        storage_connection,
        conversation_id=other_conversation.id,
        tool_name="query_snowflake",
        arguments={},
        output=None,
        error="Separate trace",
        status="error",
        provider_id="ollama",
        duration_ms=0,
    )

    assert list_tool_traces(storage_connection, conversation.id) == [first, second]
