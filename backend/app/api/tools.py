"""Tool registry API routes."""

from typing import Annotated, Any

import sqlite3
from fastapi import APIRouter, Depends

from app.database import get_database_connection
from app.models.tools import ToolExampleResponse, ToolResponse, ToolsResponse
from app.tool_registry import list_ui_tools
from tools.base import LocalTool


router = APIRouter()


TOOL_EXAMPLES: dict[str, list[ToolExampleResponse]] = {
    "summarize_findings": [
        ToolExampleResponse(
            description="Turn structured sales findings into bullets.",
            arguments={
                "findings": {
                    "row_count": 24,
                    "total_revenue": 119580,
                    "total_units": 289,
                    "average_margin_pct": 0.484,
                },
                "max_bullets": 4,
            },
        )
    ],
    "build_chart_spec": [
        ToolExampleResponse(
            description="Build a bar chart from grouped sales data.",
            arguments={
                "title": "Revenue by Region",
                "chart_type": "bar",
                "data": [
                    {"region": "South", "total_revenue": 34875},
                    {"region": "West", "total_revenue": 32710},
                ],
                "x_field": "region",
                "y_field": "total_revenue",
            },
        )
    ],
    "query_snowflake": [
        ToolExampleResponse(
            description="Run a read-only Snowflake SELECT with a row cap.",
            arguments={
                "sql": (
                    "SELECT region, SUM(CAST(revenue AS REAL)) AS total_revenue "
                    "FROM pipeline_deals WHERE stage = 'Closed Won' GROUP BY region"
                ),
                "max_rows": 10,
            },
        )
    ],
    "lookup_account": [
        ToolExampleResponse(
            description="Look up one business account by id.",
            arguments={"account_id": "AC-1001"},
        ),
        ToolExampleResponse(
            description="List all configured business accounts.",
            arguments={},
        ),
    ],
}


@router.get("/tools", response_model=ToolsResponse)
def tools(
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
) -> ToolsResponse:
    return ToolsResponse(
        tools=[_tool_to_response(tool) for tool in list_ui_tools(connection)],
    )


def _tool_to_response(tool: LocalTool) -> ToolResponse:
    return ToolResponse(
        name=tool.name,
        description=tool.description,
        parameter_schema=dict[str, Any](tool.parameter_schema),
        examples=TOOL_EXAMPLES.get(tool.name, []),
    )
