"""Findings summarization local tool."""

from collections.abc import Mapping
from typing import Any

from tools.base import LocalTool, ParameterSchema, ToolArguments, ToolOutput


SUMMARIZE_FINDINGS_PARAMETER_SCHEMA: ParameterSchema = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "object",
            "description": "Structured findings from another local tool.",
        },
        "max_bullets": {
            "type": "integer",
            "minimum": 1,
            "maximum": 8,
            "description": "Maximum number of summary bullets to return.",
        },
    },
    "required": ["findings"],
}


def run_summarize_findings(arguments: ToolArguments) -> ToolOutput:
    """Convert structured findings into short business-readable bullets."""

    findings = _findings_argument(arguments)
    max_bullets = _max_bullets_argument(arguments)
    bullets: list[str] = []

    row_count = findings.get("row_count")
    total_revenue = findings.get("total_revenue")
    total_units = findings.get("total_units")
    average_margin_pct = findings.get("average_margin_pct")

    if row_count is not None:
        bullets.append(
            f"Matched {int(row_count)} rows"
            + (
                f" with {_currency(total_revenue)} in revenue"
                if isinstance(total_revenue, int | float) else ""
            )
            + "."
        )

    if total_units is not None:
        bullets.append(f"Total units sold were {int(total_units)}.")

    if average_margin_pct is not None:
        bullets.append(f"Average margin was {_percent(average_margin_pct)}.")

    groups = findings.get("groups")
    if isinstance(groups, list) and groups:
        top_group = groups[0]
        if isinstance(top_group, Mapping):
            group_label = _group_label(top_group)
            group_revenue = top_group.get("total_revenue")
            if group_label is not None and isinstance(group_revenue, int | float):
                bullets.append(
                    f"Top segment was {group_label} at {_currency(group_revenue)}."
                )

    if not bullets:
        bullets.append("No summary metrics were available in the supplied findings.")

    return {
        "bullets": bullets[:max_bullets],
        "source_row_count": row_count if isinstance(row_count, int) else None,
    }


SUMMARIZE_FINDINGS_TOOL = LocalTool(
    name="summarize_findings",
    description="Convert structured findings into short business-readable bullets.",
    parameter_schema=SUMMARIZE_FINDINGS_PARAMETER_SCHEMA,
    run=run_summarize_findings,
)


def _max_bullets_argument(arguments: ToolArguments) -> int:
    value = arguments.get("max_bullets", 4)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("max_bullets must be an integer.")
    if value < 1 or value > 8:
        raise ValueError("max_bullets must be between 1 and 8.")
    return value


def _findings_argument(arguments: ToolArguments) -> Mapping[str, Any]:
    value = arguments.get("findings")
    if not isinstance(value, Mapping):
        raise ValueError("findings must be an object.")
    return value


def _currency(value: int | float) -> str:
    return f"${value:,.2f}"


def _percent(value: Any) -> str:
    if not isinstance(value, int | float):
        return "unknown"
    return f"{value * 100:.1f}%"


def _group_label(group: Mapping[str, Any]) -> str | None:
    skip_keys = {"total_revenue", "total_units", "row_count", "average_margin_pct"}
    for key, value in group.items():
        if key not in skip_keys and isinstance(value, str):
            return f"{key.replace('_', ' ')} {value}"
    return None
