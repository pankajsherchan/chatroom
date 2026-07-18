"""Static local tool registry (supervisor-only tools).

Runtime chat merges these with connector and dataset tools via
`app.tool_registry`. Prefer `app.tool_registry` for production execution.
"""

from collections.abc import Iterable, Mapping
from typing import Any

from tools.base import LocalTool
from tools.chart import BUILD_CHART_SPEC_TOOL
from tools.summarize import SUMMARIZE_FINDINGS_TOOL


LOCAL_TOOLS: tuple[LocalTool, ...] = (
    SUMMARIZE_FINDINGS_TOOL,
    BUILD_CHART_SPEC_TOOL,
)

TOOLS_BY_NAME: dict[str, LocalTool] = {
    tool.name: tool for tool in LOCAL_TOOLS
}


def get_tool(name: str) -> LocalTool | None:
    """Return a local tool by stable name."""

    return TOOLS_BY_NAME.get(name)


def list_tools() -> tuple[LocalTool, ...]:
    """Return all registered local tools in stable order."""

    return LOCAL_TOOLS


def list_tool_specs(tool_names: Iterable[str] | None = None) -> list[dict[str, Any]]:
    """Return provider-neutral specs for selected registered tools."""

    if tool_names is None:
        tools = LOCAL_TOOLS
    else:
        tools = []
        for name in tool_names:
            tool = get_tool(name)
            if tool is None:
                raise ValueError(f"Unknown tool: {name}")
            tools.append(tool)

    return [tool_to_spec(tool) for tool in tools]


def tool_to_spec(tool: LocalTool) -> dict[str, Any]:
    """Return the provider-neutral schema shown to model adapters."""

    return {
        "name": tool.name,
        "description": tool.description,
        "parameters": dict(tool.parameter_schema),
    }


def run_tool(name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
    """Run a registered local tool by name."""

    tool = get_tool(name)
    if tool is None:
        raise ValueError(f"Unknown tool: {name}")

    return dict(tool.run(arguments))
