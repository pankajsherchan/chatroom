import sqlite3

from app.storage import (
    Message,
    append_message,
    create_conversation,
    list_messages,
)


def test_append_message_returns_metadata(storage_connection):
    conversation = create_conversation(
        storage_connection,
        selected_agent_ids=["supervisor"],
    )

    message = append_message(
        storage_connection,
        conversation_id=conversation.id,
        role="assistant",
        content="Here is the answer.",
        agent_name="supervisor",
    )

    assert isinstance(message, Message)
    assert message.id
    assert message.conversation_id == conversation.id
    assert message.role == "assistant"
    assert message.content == "Here is the answer."
    assert message.agent_name == "supervisor"
    assert message.created_at


def test_list_messages_returns_conversation_messages_in_insert_order(storage_connection):
    conversation = create_conversation(
        storage_connection,
        selected_agent_ids=["supervisor"],
    )
    other_conversation = create_conversation(
        storage_connection,
        selected_agent_ids=["summarizer"],
    )

    first = append_message(
        storage_connection,
        conversation_id=conversation.id,
        role="user",
        content="Summarize sales",
    )
    second = append_message(
        storage_connection,
        conversation_id=conversation.id,
        role="assistant",
        content="Sales are up.",
        agent_name="summarizer",
    )
    append_message(
        storage_connection,
        conversation_id=other_conversation.id,
        role="user",
        content="Separate thread",
    )

    messages = list_messages(storage_connection, conversation.id)

    assert messages == [first, second]


def test_append_message_requires_existing_conversation(storage_connection):
    try:
        append_message(
            storage_connection,
            conversation_id="missing",
            role="user",
            content="hello",
        )
    except sqlite3.IntegrityError:
        pass
    else:
        raise AssertionError("Expected foreign key failure for missing conversation")
