"""Local agent metadata models and static registry helpers."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class LocalAgent:
    """Metadata the backend needs to expose or run a local agent."""

    id: str
    name: str
    description: str
    system_prompt: str
    tools: tuple[str, ...] = ()


@dataclass(frozen=True)
class LocalTeam:
    """Predefined local group-chat team made from registered agents."""

    id: str
    name: str
    description: str
    agent_ids: tuple[str, ...]


LOCAL_AGENTS = MappingProxyType(
    {
        "supervisor": LocalAgent(
            id="supervisor",
            name="Supervisor Agent",
            description=(
                "Supervisor group agent that delegates to specialists and synthesizes the "
                "final response."
            ),
            system_prompt=(
                "You are the supervisor agent. Route the user's request to the "
                "right specialist agents, combine their findings, and answer as one team."
            ),
            tools=(),
        ),
    }
)

SUPERVISOR_TEAM_AGENT_IDS: tuple[str, ...] = ()

LOCAL_TEAMS = MappingProxyType({})


def list_agents() -> list[LocalAgent]:
    """Return all local agents in registry order."""

    return list(LOCAL_AGENTS.values())


def get_agent(agent_id: str) -> LocalAgent | None:
    """Look up one local agent by id."""

    return LOCAL_AGENTS.get(agent_id)


def get_supervisor_team() -> tuple[LocalAgent, ...]:
    """Return the specialist agents coordinated by supervisor."""

    return tuple(LOCAL_AGENTS[agent_id] for agent_id in SUPERVISOR_TEAM_AGENT_IDS)


def list_teams() -> list[LocalTeam]:
    """Return predefined local teams in registry order."""

    return list(LOCAL_TEAMS.values())


def get_team(team_id: str) -> LocalTeam | None:
    """Look up one predefined team by id."""

    return LOCAL_TEAMS.get(team_id)
