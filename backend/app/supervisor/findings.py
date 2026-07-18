"""Helpers for extracting chartable and summarizable tool findings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from app.models.supervisor import AgentRunResult


def _findings_for_summarize(
    agent_results: Sequence[AgentRunResult],
) -> Mapping[str, Any]:
    output = _latest_findings(agent_results)
    if not output:
        return {}

    if any(key in output for key in ("total_revenue", "total_units", "groups")):
        return output

    row_count = output.get("row_count")
    if isinstance(row_count, int):
        return {"row_count": row_count}

    rows = output.get("rows")
    if isinstance(rows, list):
        return {"row_count": len(rows)}

    return output


def _latest_findings(agent_results: Sequence[AgentRunResult]) -> Mapping[str, Any]:
    for result in reversed(agent_results):
        for tool_output in reversed(result.tool_outputs):
            output = tool_output.get("output")
            if isinstance(output, Mapping):
                return output
    return {}


def _latest_chart_findings(
    agent_results: Sequence[AgentRunResult],
) -> Mapping[str, Any]:
    grouped = _latest_grouped_findings(agent_results)
    if grouped:
        return grouped

    for result in reversed(agent_results):
        for tool_output in reversed(result.tool_outputs):
            output = tool_output.get("output")
            if not isinstance(output, Mapping):
                continue
            chart_findings = _tabular_chart_findings(output)
            if chart_findings:
                return chart_findings

    return {}


def _tabular_chart_findings(output: Mapping[str, Any]) -> Mapping[str, Any]:
    rows = output.get("rows")
    columns = output.get("columns")
    if not isinstance(rows, list) or not rows:
        return {}
    if not isinstance(columns, list) or len(columns) < 2:
        return {}

    x_field = columns[0]
    y_field = _first_numeric_column(columns[1:], rows)
    if y_field is None:
        return {}

    groups: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        y_value = _coerce_number(row.get(y_field))
        if y_value is None:
            continue
        groups.append(
            {
                x_field: row.get(x_field),
                "total_revenue": y_value,
            }
        )

    if not groups:
        return {}

    return {"group_by": x_field, "groups": groups}


def _latest_grouped_findings(agent_results: Sequence[AgentRunResult]) -> Mapping[str, Any]:
    for result in reversed(agent_results):
        for tool_output in reversed(result.tool_outputs):
            output = tool_output.get("output")
            if (
                isinstance(output, Mapping)
                and isinstance(output.get("group_by"), str)
                and isinstance(output.get("groups"), list)
            ):
                return output
    return {}


def _summary_content(output: Mapping[str, Any]) -> str:
    bullets = output.get("bullets")
    if not isinstance(bullets, list) or not bullets:
        return "Summarizer did not find summary metrics."
    return "Summarizer prepared:\n" + "\n".join(f"- {bullet}" for bullet in bullets)


def _chart_arguments(findings: Mapping[str, Any], user_input: str) -> dict[str, Any]:
    group_by = findings.get("group_by")
    groups = findings.get("groups")
    if not isinstance(group_by, str) or not isinstance(groups, list) or not groups:
        raise ValueError("Visualizer requires grouped data findings.")

    chart_type = "line" if "line" in user_input.casefold() else "bar"
    return {
        "title": _chart_title(group_by, chart_type),
        "chart_type": chart_type,
        "data": groups,
        "x_field": group_by,
        "y_field": "total_revenue",
    }


def _chart_title(group_by: str, chart_type: str) -> str:
    label = group_by.replace("_", " ").title()
    return f"Revenue by {label} ({chart_type})"


def _coerce_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None

def _first_numeric_column(
    columns: Sequence[str],
    rows: Sequence[Mapping[str, Any]],
) -> str | None:
    for column in columns:
        if any(_coerce_number(row.get(column)) is not None for row in rows):
            return column
    return None
