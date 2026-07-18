"""Shared specialist-team selection for supervisor routing."""

from __future__ import annotations

from app.agent_registry import is_specialist_agent_id
from app.agents import SUPERVISOR_TEAM_AGENT_IDS
from app.models.supervisor import SupervisorRequest


def allowed_specialist_ids(request: SupervisorRequest) -> tuple[str, ...]:
    """Return the specialist agent ids available for one supervised turn."""

    selected = tuple(request.selected_agent_ids)
    if not selected or "supervisor" in selected:
        builtin_ids = SUPERVISOR_TEAM_AGENT_IDS
        custom_ids = tuple(
            agent_id
            for agent_id in request.agent_catalog
            if is_specialist_agent_id(agent_id)
        )
        return builtin_ids + custom_ids

    return tuple(
        agent_id
        for agent_id in selected
        if agent_id != "supervisor" and agent_id in request.agent_catalog
    )
