"""Merge built-in and custom agent metadata at the API boundary."""

from __future__ import annotations

import sqlite3

from app.agents import LOCAL_AGENTS, LocalAgent, LocalTeam, get_agent, list_agents, list_teams
from app.connector_agents import (
    get_connector_agent,
    is_connector_agent_id,
    list_connector_agents,
)
from app.settings import get_settings
from app.storage import CustomAgentRecord, get_custom_agent, list_custom_agents


def custom_agent_to_local_agent(record: CustomAgentRecord) -> LocalAgent:
    return LocalAgent(
        id=record.id,
        name=record.name,
        description=record.description,
        system_prompt=record.system_prompt,
        tools=tuple(record.tools),
    )


def resolve_agent(
    connection: sqlite3.Connection,
    agent_id: str,
) -> LocalAgent | None:
    builtin = get_agent(agent_id)
    if builtin is not None:
        return builtin

    connector_agent = get_connector_agent(agent_id)
    if connector_agent is not None:
        return connector_agent

    custom = get_custom_agent(connection, agent_id)
    if custom is None:
        return None

    return custom_agent_to_local_agent(custom)


def list_all_agents(connection: sqlite3.Connection) -> list[LocalAgent]:
    return [
        *list_agents(),
        *list_connector_agents(get_settings()),
        *map(custom_agent_to_local_agent, list_custom_agents(connection)),
    ]


def list_all_teams(connection: sqlite3.Connection) -> list[LocalTeam]:
    teams = list(list_teams())
    custom_records = list_custom_agents(connection)
    if not custom_records:
        return teams

    teams.append(
        LocalTeam(
            id="custom_agents",
            name="Custom Agents",
            description="Run all of your saved custom specialists together.",
            agent_ids=tuple(record.id for record in custom_records),
        )
    )

    for record in custom_records:
        teams.append(
            LocalTeam(
                id=f"team_{record.id}",
                name=record.name,
                description=record.description,
                agent_ids=(record.id,),
            )
        )

    return teams


def team_source(team: LocalTeam) -> str:
    if team.id == "custom_agents" or team.id.startswith("team_custom_"):
        return "custom"
    return "builtin"


def build_agent_catalog(
    connection: sqlite3.Connection,
    selected_agent_ids: list[str],
) -> dict[str, LocalAgent]:
    catalog: dict[str, LocalAgent] = {}
    for agent_id in selected_agent_ids:
        agent = resolve_agent(connection, agent_id)
        if agent is not None:
            catalog[agent_id] = agent
    return catalog


def is_custom_agent_id(agent_id: str) -> bool:
    return agent_id.startswith("custom_")


def is_specialist_agent_id(agent_id: str) -> bool:
    return is_custom_agent_id(agent_id) or is_connector_agent_id(agent_id)
