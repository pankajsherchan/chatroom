"""Deterministic specialist routing rules."""

from collections.abc import Mapping, Sequence

from app.agent_registry import is_custom_agent_id, is_specialist_agent_id
from app.agents import LocalAgent
from app.models.supervisor import SupervisorRequest
from app.supervisor.team import allowed_specialist_ids


SUMMARIZE_KEYWORDS: tuple[str, ...] = (
    "brief",
    "bullet",
    "bullets",
    "explain",
    "findings",
    "recap",
    "summarize",
    "summary",
)

VISUALIZE_KEYWORDS: tuple[str, ...] = (
    "bar",
    "chart",
    "graph",
    "line",
    "plot",
    "trend",
    "visual",
    "visualize",
)


def prompt_wants_summarize(prompt: str) -> bool:
    lowered = prompt.casefold()
    return any(keyword in lowered for keyword in SUMMARIZE_KEYWORDS)


def prompt_wants_visualize(prompt: str) -> bool:
    lowered = prompt.casefold()
    return any(keyword in lowered for keyword in VISUALIZE_KEYWORDS)


def stable_specialist_order(agent_ids: Sequence[str]) -> tuple[str, ...]:
    """Preserve the routed specialist order."""

    return tuple(agent_ids)


def route_agent_ids(request: SupervisorRequest) -> tuple[str, ...]:
    """Choose specialist agent ids from a request using deterministic rules."""

    allowed_agent_ids = allowed_specialist_ids(request)
    if not allowed_agent_ids:
        return ()

    prompt = request.user_input.casefold()
    routed_agent_ids = tuple(
        agent_id
        for agent_id in allowed_agent_ids
        if _prompt_matches_agent(prompt, agent_id, request.agent_catalog)
    )

    if routed_agent_ids:
        return routed_agent_ids

    specialist_agent_ids = tuple(
        agent_id for agent_id in allowed_agent_ids if is_specialist_agent_id(agent_id)
    )
    if specialist_agent_ids:
        return specialist_agent_ids

    return allowed_agent_ids[:1]


def _prompt_matches_agent(
    prompt: str,
    agent_id: str,
    agent_catalog: Mapping[str, LocalAgent],
) -> bool:
    if not is_custom_agent_id(agent_id):
        return False

    agent = agent_catalog.get(agent_id)
    if agent is None:
        return False

    haystack = f"{agent.name} {agent.description} {agent.system_prompt}".casefold()
    tokens = [token for token in prompt.split() if len(token) > 3]
    return any(token in haystack for token in tokens) or prompt in haystack
