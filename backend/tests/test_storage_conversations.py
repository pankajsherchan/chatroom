from app.storage import (
    Conversation,
    create_conversation,
    get_conversation,
    list_conversations,
)


def test_create_conversation_returns_metadata(storage_connection):
    conversation = create_conversation(
        storage_connection,
        title="Sales analysis",
        selected_agent_ids=["supervisor"],
    )

    assert isinstance(conversation, Conversation)
    assert conversation.id
    assert conversation.title == "Sales analysis"
    assert conversation.selected_agent_ids == ["supervisor"]
    assert conversation.created_at


def test_get_conversation_returns_metadata_or_none(storage_connection):
    created = create_conversation(
        storage_connection,
        title="Summary",
        selected_agent_ids=["supervisor"],
    )

    found = get_conversation(storage_connection, created.id)

    assert found == created
    assert get_conversation(storage_connection, "missing") is None


def test_list_conversations_returns_all_metadata(storage_connection):
    first = create_conversation(
        storage_connection,
        title="First",
        selected_agent_ids=["supervisor"],
    )
    second = create_conversation(
        storage_connection,
        title="Second",
        selected_agent_ids=["supervisor"],
    )

    conversations = list_conversations(storage_connection)

    assert {conversation.id for conversation in conversations} == {first.id, second.id}
    assert {conversation.title for conversation in conversations} == {"First", "Second"}
