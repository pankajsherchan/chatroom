"""Merge static, optional connector, and imported-dataset tools.

This is the runtime tool facade used by chat. Static tools alone live in
`tools.registry`.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from app.connectors.external_api import external_api_is_configured
from app.connectors.snowflake import snowflake_is_configured
from app.settings import Settings, get_settings
from app.storage import ImportedDatasetRecord, get_imported_dataset_by_tool_name, list_imported_datasets
from tools.base import LocalTool
from tools.imported_dataset import build_dataset_tool
from tools.lookup_account import LOOKUP_ACCOUNT_TOOL
from tools.registry import get_tool as get_static_tool
from tools.registry import list_tools as list_static_tools
from tools.registry import tool_to_spec
from tools.snowflake_query import QUERY_SNOWFLAKE_TOOL


SUPERVISOR_ONLY_TOOL_NAMES = frozenset({"summarize_findings", "build_chart_spec"})


_bound_connection: ContextVar[sqlite3.Connection | None] = ContextVar("_bound_connection", default=None)


@contextmanager
def tool_connection_scope(connection: sqlite3.Connection):
    token = _bound_connection.set(connection)
    try:
        yield
    finally:
        _bound_connection.reset(token)


def list_optional_tools(settings: Settings | None = None) -> tuple[LocalTool, ...]:
    settings = settings or get_settings()
    tools: list[LocalTool] = []
    if snowflake_is_configured(settings):
        tools.append(QUERY_SNOWFLAKE_TOOL)
    if external_api_is_configured(settings):
        tools.append(LOOKUP_ACCOUNT_TOOL)
    return tuple(tools)


def list_all_tools(
    connection: sqlite3.Connection | None = None,
    *,
    settings: Settings | None = None,
) -> tuple[LocalTool, ...]:
    conn = connection or _bound_connection.get()
    settings = settings or get_settings()
    tools: list[LocalTool] = [*list_static_tools(), *list_optional_tools(settings)]
    if conn is not None:
        tools.extend(list_dataset_tools(conn))
    return tuple(tools)


def list_ui_tools(
    connection: sqlite3.Connection | None = None,
    *,
    settings: Settings | None = None,
) -> tuple[LocalTool, ...]:
    """Return tools exposed in the UI for custom-agent assignment."""

    return tuple(
        tool
        for tool in list_all_tools(connection, settings=settings)
        if tool.name not in SUPERVISOR_ONLY_TOOL_NAMES
    )


def list_dataset_tools(connection: sqlite3.Connection) -> tuple[LocalTool, ...]:
    return tuple(_dataset_record_to_tool(record) for record in list_imported_datasets(connection))


def resolve_tool(
    name: str,
    connection: sqlite3.Connection | None = None,
    *,
    settings: Settings | None = None,
) -> LocalTool | None:
    static_tool = get_static_tool(name)
    if static_tool is not None:
        return static_tool

    settings = settings or get_settings()
    if name == QUERY_SNOWFLAKE_TOOL.name and snowflake_is_configured(settings):
        return QUERY_SNOWFLAKE_TOOL
    if name == LOOKUP_ACCOUNT_TOOL.name and external_api_is_configured(settings):
        return LOOKUP_ACCOUNT_TOOL

    conn = connection or _bound_connection.get()
    if conn is None:
        return None

    record = get_imported_dataset_by_tool_name(conn, name)
    if record is None:
        return None
    return _dataset_record_to_tool(record)


def list_tool_specs(
    tool_names: Iterable[str] | None = None,
    *,
    connection: sqlite3.Connection | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    if tool_names is None:
        tools = list_all_tools(connection, settings=settings)
    else:
        tools = []
        for name in tool_names:
            tool = resolve_tool(name, connection, settings=settings)
            if tool is None:
                raise ValueError(f"Unknown tool: {name}")
            tools.append(tool)

    return [tool_to_spec(tool) for tool in tools]


def run_registered_tool(
    name: str,
    arguments: Mapping[str, Any],
    *,
    connection: sqlite3.Connection | None = None,
    settings: Settings | None = None,
) -> dict[str, Any]:
    tool = resolve_tool(name, connection, settings=settings)
    if tool is None:
        raise ValueError(f"Unknown tool: {name}")
    return dict(tool.run(arguments))


def validate_tool_names(
    connection: sqlite3.Connection,
    tool_names: list[str],
    *,
    settings: Settings | None = None,
) -> list[str]:
    settings = settings or get_settings()
    reserved = [
        tool_name
        for tool_name in tool_names
        if tool_name in SUPERVISOR_ONLY_TOOL_NAMES
    ]
    if reserved:
        raise ValueError(
            "Tools reserved for supervisor follow-up: "
            f"{', '.join(reserved)}."
        )
    unknown = [
        tool_name
        for tool_name in tool_names
        if resolve_tool(tool_name, connection, settings=settings) is None
    ]
    if unknown:
        raise ValueError(f"Unknown tools: {', '.join(unknown)}")
    return tool_names


def _dataset_record_to_tool(record: ImportedDatasetRecord) -> LocalTool:
    return build_dataset_tool(
        dataset_id=record.id,
        name=record.name,
        description=record.description,
        file_path=record.file_path,
        columns=record.columns,
    )
