from app.storage import (
    create_custom_agent,
    delete_custom_agent,
    get_custom_agent,
    list_custom_agents,
    update_custom_agent,
)


def test_create_custom_agent_persists_metadata(storage_connection):
    created = create_custom_agent(
        storage_connection,
        name="Pricing Analyst",
        description="Focuses on pricing and revenue questions.",
        system_prompt="You analyze pricing trends from local sales data.",
        tools=["lookup_account"],
    )

    assert created.id.startswith("custom_")
    assert created.name == "Pricing Analyst"
    assert created.tools == ["lookup_account"]

    stored = get_custom_agent(storage_connection, created.id)
    assert stored == created


def test_list_custom_agents_returns_newest_first(storage_connection):
    first = create_custom_agent(
        storage_connection,
        name="First",
        description="First custom agent",
        system_prompt="Prompt one",
        tools=[],
    )
    second = create_custom_agent(
        storage_connection,
        name="Second",
        description="Second custom agent",
        system_prompt="Prompt two",
        tools=["lookup_account"],
    )

    agents = list_custom_agents(storage_connection)

    assert {agent.id for agent in agents} == {first.id, second.id}
    assert {agent.name for agent in agents} == {"First", "Second"}


def test_update_custom_agent_changes_metadata(storage_connection):
    created = create_custom_agent(
        storage_connection,
        name="Original",
        description="Original description",
        system_prompt="Original prompt",
        tools=[],
    )

    updated = update_custom_agent(
        storage_connection,
        created.id,
        name="Updated",
        description="Updated description",
        system_prompt="Updated prompt",
        tools=["lookup_account"],
    )

    assert updated is not None
    assert updated.id == created.id
    assert updated.name == "Updated"
    assert updated.tools == ["lookup_account"]
    assert updated.updated_at >= created.updated_at


def test_delete_custom_agent_removes_record(storage_connection):
    created = create_custom_agent(
        storage_connection,
        name="Delete me",
        description="Temporary custom agent",
        system_prompt="Prompt",
        tools=[],
    )

    deleted = delete_custom_agent(storage_connection, created.id)

    assert deleted is True
    assert get_custom_agent(storage_connection, created.id) is None
