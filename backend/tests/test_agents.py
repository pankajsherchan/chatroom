from dataclasses import FrozenInstanceError

import pytest

from app.agents import (
    LOCAL_AGENTS,
    LOCAL_TEAMS,
    SUPERVISOR_TEAM_AGENT_IDS,
    LocalAgent,
    LocalTeam,
    get_agent,
    get_supervisor_team,
    get_team,
    list_agents,
    list_teams,
)


def test_local_agent_captures_required_metadata():
    agent = LocalAgent(
        id="custom_analyst",
        name="Custom Analyst",
        description="Runs connector-backed analysis.",
        system_prompt="Use configured tools to answer questions.",
        tools=("query_snowflake", "lookup_account"),
    )

    assert agent.id == "custom_analyst"
    assert agent.tools == ("query_snowflake", "lookup_account")


def test_local_agent_defaults_to_no_tools():
    agent = LocalAgent(
        id="custom_helper",
        name="Custom Helper",
        description="A helper without tools.",
        system_prompt="Write clear answers.",
    )

    assert agent.tools == ()

    with pytest.raises(FrozenInstanceError):
        agent.name = "Different name"


def test_static_agent_registry_includes_supervisor_only():
    agents = list_agents()

    assert [agent.id for agent in agents] == ["supervisor"]


def test_registry_supervisor_has_no_tools():
    supervisor = get_agent("supervisor")

    assert supervisor is not None
    assert supervisor.tools == ()


def test_get_agent_returns_none_for_unknown_agent():
    assert get_agent("unknown") is None


def test_supervisor_team_is_empty():
    team = get_supervisor_team()

    assert SUPERVISOR_TEAM_AGENT_IDS == ()
    assert team == ()


def test_predefined_team_registry_is_empty():
    assert list_teams() == []
    assert get_team("missing") is None


def test_static_agent_registry_is_read_only():
    with pytest.raises(TypeError):
        LOCAL_AGENTS["new_agent"] = LocalAgent(
            id="new_agent",
            name="New Agent",
            description="Not part of the static registry.",
            system_prompt="Do not add this.",
        )

    with pytest.raises(TypeError):
        LOCAL_TEAMS["new_team"] = LocalTeam(
            id="new_team",
            name="New Team",
            description="Not part of the static registry.",
            agent_ids=("custom_test",),
        )
