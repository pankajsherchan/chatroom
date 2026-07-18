from app.storage import (
    append_message,
    connect_database,
    create_conversation,
    get_conversation,
    list_messages,
)


def test_conversation_and_messages_persist_after_reopening_database(tmp_path):
    db_path = tmp_path / "chatroom.sqlite3"
    first_connection = connect_database(db_path)
    conversation = create_conversation(
        first_connection,
        title="Persistent chat",
        selected_agent_ids=["supervisor", "summarizer"],
    )
    user_message = append_message(
        first_connection,
        conversation_id=conversation.id,
        role="user",
        content="Summarize the sales data.",
    )
    assistant_message = append_message(
        first_connection,
        conversation_id=conversation.id,
        role="assistant",
        content="Sales are trending upward.",
        agent_name="summarizer",
    )
    first_connection.close()

    second_connection = connect_database(db_path)

    assert get_conversation(second_connection, conversation.id) == conversation
    assert list_messages(second_connection, conversation.id) == [
        user_message,
        assistant_message,
    ]

    second_connection.close()
