"""Custom agent CRUD API routes."""

from typing import Annotated

import sqlite3
from fastapi import APIRouter, Depends, HTTPException

from app.database import get_database_connection
from app.models.custom_agents import (
    CreateCustomAgentRequest,
    CustomAgentResponse,
    UpdateCustomAgentRequest,
)
from app.storage import (
    CustomAgentRecord,
    create_custom_agent,
    delete_custom_agent,
    get_custom_agent,
    list_custom_agents,
    update_custom_agent,
)
from app.tool_registry import validate_tool_names


router = APIRouter()


@router.get("/custom-agents", response_model=list[CustomAgentResponse])
def custom_agents_list(
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
):
    return [_custom_agent_to_response(agent) for agent in list_custom_agents(connection)]


@router.post("/custom-agents", response_model=CustomAgentResponse, status_code=201)
def custom_agents_create(
    request: CreateCustomAgentRequest,
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
):
    try:
        validate_tool_names(connection, request.tools)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    created = create_custom_agent(
        connection,
        name=request.name.strip(),
        description=request.description.strip(),
        system_prompt=request.system_prompt.strip(),
        tools=request.tools,
    )
    return _custom_agent_to_response(created)


@router.get("/custom-agents/{agent_id}", response_model=CustomAgentResponse)
def custom_agent_detail(
    agent_id: str,
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
):
    found = get_custom_agent(connection, agent_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"Custom agent not found: {agent_id}")
    return _custom_agent_to_response(found)


@router.put("/custom-agents/{agent_id}", response_model=CustomAgentResponse)
def custom_agents_update(
    agent_id: str,
    request: UpdateCustomAgentRequest,
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
):
    try:
        validate_tool_names(connection, request.tools)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    updated = update_custom_agent(
        connection,
        agent_id,
        name=request.name.strip(),
        description=request.description.strip(),
        system_prompt=request.system_prompt.strip(),
        tools=request.tools,
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Custom agent not found: {agent_id}")
    return _custom_agent_to_response(updated)


@router.delete("/custom-agents/{agent_id}", status_code=204)
def custom_agents_delete(
    agent_id: str,
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
):
    deleted = delete_custom_agent(connection, agent_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Custom agent not found: {agent_id}")


def _custom_agent_to_response(record: CustomAgentRecord) -> CustomAgentResponse:
    return CustomAgentResponse(
        id=record.id,
        name=record.name,
        description=record.description,
        system_prompt=record.system_prompt,
        tools=record.tools,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
