"""Default argument policies for specialist tools."""

from __future__ import annotations

from typing import Any


# Dataset tools still use inferred defaults until model-driven args are wired.
DEFAULT_DATASET_QUERY_ARGUMENTS: dict[str, Any] = {"limit": 50}


def default_arguments_for_tool(tool_name: str) -> dict[str, Any] | None:
    """Return safe default args for tools that skip provider tool-calls.

    Returns None when the tool requires model-generated arguments.
    """

    if tool_name.startswith("query_dataset_"):
        return dict(DEFAULT_DATASET_QUERY_ARGUMENTS)
    return None
