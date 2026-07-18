"""Agent registry API routes."""

from typing import Annotated

import sqlite3
from fastapi import APIRouter, Depends

from app.agent_registry import list_all_agents, list_all_teams, team_source
from app.connector_agents import is_connector_agent_id
from app.agents import SUPERVISOR_TEAM_AGENT_IDS, LocalAgent, LocalTeam
from app.database import get_database_connection


router = APIRouter()


@router.get("/agents")
def agents(
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
):
    return {
        "agents": [_agent_to_response(agent) for agent in list_all_agents(connection)],
        "teams": [_team_to_response(team) for team in list_all_teams(connection)],
        "supervisor_agent_id": "supervisor",
        "supervisor_team_agent_ids": list(SUPERVISOR_TEAM_AGENT_IDS),
    }


def _agent_to_response(agent: LocalAgent) -> dict[str, object]:
    return {
        "id": agent.id,
        "name": agent.name,
        "description": agent.description,
        "system_prompt": agent.system_prompt,
        "tools": list(agent.tools),
        "source": _agent_source(agent.id),
    }


def _agent_source(agent_id: str) -> str:
    if agent_id.startswith("custom_"):
        return "custom"
    if is_connector_agent_id(agent_id):
        return "connector"
    return "builtin"


def _team_to_response(team: LocalTeam) -> dict[str, object]:
    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "agent_ids": list(team.agent_ids),
        "source": team_source(team),
    }
