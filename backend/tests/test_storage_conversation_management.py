from app.storage import (
    Conversation,
    append_artifact,
    append_group_chat_event,
    append_message,
    append_tool_trace,
    create_conversation,
    delete_conversation,
    get_conversation,
    list_artifacts,
    list_group_chat_events,
    list_messages,
    list_tool_traces,
    update_conversation_title,
)


def test_update_conversation_title_returns_updated_metadata(storage_connection):
    created = create_conversation(
        storage_connection,
        title="Original",
        selected_agent_ids=["supervisor"],
    )

    updated = update_conversation_title(
        storage_connection,
        created.id,
        title="Bedrock comparison",
    )

    assert isinstance(updated, Conversation)
    assert updated.id == created.id
    assert updated.title == "Bedrock comparison"
    assert updated.selected_agent_ids == ["supervisor"]
    assert get_conversation(storage_connection, created.id) == updated


def test_update_conversation_title_returns_none_for_missing_conversation(storage_connection):
    assert (
        update_conversation_title(
            storage_connection,
            "missing",
            title="Does not matter",
        )
        is None
    )


def test_delete_conversation_removes_conversation_and_related_rows(storage_connection):
    created = create_conversation(
        storage_connection,
        title="Delete me",
        selected_agent_ids=["supervisor"],
    )
    message = append_message(
        storage_connection,
        conversation_id=created.id,
        role="user",
        content="Hello",
    )
    append_tool_trace(
        storage_connection,
        conversation_id=created.id,
        tool_name="query_snowflake",
        arguments={},
        output={"row_count": 0},
        error=None,
        status="success",
        provider_id="ollama",
        duration_ms=5,
    )
    append_group_chat_event(
        storage_connection,
        conversation_id=created.id,
        event_type="final_answer",
        agent_id=None,
        content="Done",
        payload={},
    )
    append_artifact(
        storage_connection,
        conversation_id=created.id,
        message_id=message.id,
        artifact_type="chart",
        title="Chart",
        payload={"spec": {"chart_type": "bar", "series": []}},
    )

    deleted = delete_conversation(storage_connection, created.id)

    assert deleted is True
    assert get_conversation(storage_connection, created.id) is None
    assert list_messages(storage_connection, created.id) == []
    assert list_tool_traces(storage_connection, created.id) == []
    assert list_group_chat_events(storage_connection, created.id) == []
    assert list_artifacts(storage_connection, created.id) == []


def test_delete_conversation_returns_false_for_missing_conversation(storage_connection):
    assert delete_conversation(storage_connection, "missing") is False
