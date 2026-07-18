"""Chart specification local tool."""

from collections.abc import Mapping
from typing import Any

from tools.base import LocalTool, ParameterSchema, ToolArguments, ToolOutput


BUILD_CHART_SPEC_PARAMETER_SCHEMA: ParameterSchema = {
    "type": "object",
    "properties": {
        "title": {
            "type": "string",
            "description": "Chart title.",
        },
        "chart_type": {
            "type": "string",
            "enum": ["bar", "line"],
            "description": "Simple chart type.",
        },
        "data": {
            "type": "array",
            "description": "Rows to plot.",
            "items": {"type": "object"},
        },
        "x_field": {
            "type": "string",
            "description": "Field to use for x-axis labels.",
        },
        "y_field": {
            "type": "string",
            "description": "Numeric field to use for y-axis values.",
        },
    },
    "required": ["data", "x_field", "y_field"],
}


def run_build_chart_spec(arguments: ToolArguments) -> ToolOutput:
    """Build a simple chart specification from structured rows."""

    data = _chart_data_argument(arguments)
    x_field = _required_string_argument(arguments, "x_field")
    y_field = _required_string_argument(arguments, "y_field")
    chart_type = _chart_type_argument(arguments)
    title = _optional_string_argument(arguments, "title") or _default_chart_title(
        chart_type,
        x_field,
        y_field,
    )

    series = []
    for row in data:
        if x_field not in row:
            raise ValueError(f"x_field {x_field!r} is missing from a data row.")
        if y_field not in row:
            raise ValueError(f"y_field {y_field!r} is missing from a data row.")
        y_value = row[y_field]
        if isinstance(y_value, bool) or not isinstance(y_value, int | float):
            raise ValueError(f"y_field {y_field!r} must contain numeric values.")
        series.append(
            {
                "label": str(row[x_field]),
                "value": float(y_value),
            }
        )

    return {
        "chart_type": chart_type,
        "title": title,
        "x_field": x_field,
        "y_field": y_field,
        "series": series,
    }


BUILD_CHART_SPEC_TOOL = LocalTool(
    name="build_chart_spec",
    description="Build a simple chart specification from structured rows.",
    parameter_schema=BUILD_CHART_SPEC_PARAMETER_SCHEMA,
    run=run_build_chart_spec,
)


def _chart_data_argument(arguments: ToolArguments) -> list[Mapping[str, Any]]:
    value = arguments.get("data")
    if not isinstance(value, list) or not value:
        raise ValueError("data must be a non-empty list of objects.")
    if not all(isinstance(row, Mapping) for row in value):
        raise ValueError("data must be a non-empty list of objects.")
    return value


def _required_string_argument(arguments: ToolArguments, name: str) -> str:
    value = arguments.get(name)
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"{name} must be a non-empty string.")
    return value.strip()


def _optional_string_argument(arguments: ToolArguments, name: str) -> str | None:
    value = arguments.get(name)
    if value is None:
        return None
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError(f"{name} must be a non-empty string when provided.")
    return value.strip()


def _chart_type_argument(arguments: ToolArguments) -> str:
    value = arguments.get("chart_type", "bar")
    if value not in {"bar", "line"}:
        raise ValueError("chart_type must be one of: bar, line.")
    return value


def _default_chart_title(chart_type: str, x_field: str, y_field: str) -> str:
    return f"{y_field.replace('_', ' ').title()} by {x_field.replace('_', ' ').title()} ({chart_type})"
