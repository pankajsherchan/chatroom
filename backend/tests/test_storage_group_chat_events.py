from app.storage import (
    GroupChatEventRecord,
    append_group_chat_event,
    create_conversation,
    list_group_chat_events,
)


def test_append_group_chat_event_returns_metadata(storage_connection):
    conversation = create_conversation(
        storage_connection,
        selected_agent_ids=["supervisor"],
    )

    event = append_group_chat_event(
        storage_connection,
        conversation_id=conversation.id,
        event_type="specialist_selected",
        agent_id="data_analyst",
        content="Analyze revenue by region.",
        payload={"target_agent_id": "data_analyst"},
    )

    assert isinstance(event, GroupChatEventRecord)
    assert event.id
    assert event.conversation_id == conversation.id
    assert event.event_type == "specialist_selected"
    assert event.agent_id == "data_analyst"
    assert event.content == "Analyze revenue by region."
    assert event.payload == {"target_agent_id": "data_analyst"}
    assert event.created_at


def test_list_group_chat_events_returns_conversation_events_in_insert_order(
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

    first = append_group_chat_event(
        storage_connection,
        conversation_id=conversation.id,
        event_type="manager_started",
        agent_id=None,
        content="Supervisor started a local group-chat turn.",
        payload={"called_agent_ids": ["data_analyst"]},
    )
    second = append_group_chat_event(
        storage_connection,
        conversation_id=conversation.id,
        event_type="final_answer",
        agent_id=None,
        content="Done.",
        payload={"artifact_count": 0},
    )
    append_group_chat_event(
        storage_connection,
        conversation_id=other_conversation.id,
        event_type="final_answer",
        agent_id=None,
        content="Separate.",
        payload={},
    )

    assert list_group_chat_events(storage_connection, conversation.id) == [
        first,
        second,
    ]
