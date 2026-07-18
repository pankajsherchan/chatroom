"""Generic query tool factory for imported CSV datasets."""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from tools.base import LocalTool, ParameterSchema, ToolArguments, ToolOutput
from tools.csv_schema import DatasetColumn


def dataset_tool_name(dataset_id: str) -> str:
    return f"query_{dataset_id.replace('-', '_')}"


def build_dataset_tool(
    *,
    dataset_id: str,
    name: str,
    description: str,
    file_path: Path,
    columns: Sequence[DatasetColumn],
) -> LocalTool:
    string_columns = [column.name for column in columns if column.column_type == "string"]
    numeric_columns = [column.name for column in columns if column.column_type == "number"]

    def run(arguments: ToolArguments) -> ToolOutput:
        return run_dataset_query(
            file_path=file_path,
            columns=columns,
            string_columns=string_columns,
            numeric_columns=numeric_columns,
            arguments=arguments,
        )

    return LocalTool(
        name=dataset_tool_name(dataset_id),
        description=description or f"Filter and summarize the imported dataset {name}.",
        parameter_schema=_parameter_schema(string_columns),
        run=run,
    )


def run_dataset_query(
    *,
    file_path: Path,
    columns: Sequence[DatasetColumn],
    string_columns: Sequence[str],
    numeric_columns: Sequence[str],
    arguments: ToolArguments,
) -> ToolOutput:
    filters = _filters_argument(arguments, string_columns)
    group_by = _optional_group_by(arguments, string_columns)
    limit = _limit_argument(arguments)

    rows = [_parse_row(raw_row, columns) for raw_row in _load_csv_rows(file_path)]
    rows = [row for row in rows if _row_matches_filters(row, filters)]
    summary = _summarize_rows(rows, numeric_columns)

    if group_by is not None:
        groups = _group_rows(rows, group_by, numeric_columns)
        return {
            "filters": filters,
            "group_by": group_by,
            **summary,
            "groups": groups[:limit],
        }

    return {
        "filters": filters,
        "group_by": None,
        **summary,
        "rows": rows[:limit],
    }


def _parameter_schema(string_columns: Sequence[str]) -> ParameterSchema:
    properties: dict[str, Any] = {
        "limit": {
            "type": "integer",
            "minimum": 1,
            "maximum": 50,
            "description": "Maximum number of detail rows or groups to return.",
        }
    }

    if string_columns:
        properties["filters"] = {
            "type": "object",
            "description": "Exact-match filters for string columns.",
            "properties": {column: {"type": "string"} for column in string_columns},
            "additionalProperties": False,
        }
        properties["group_by"] = {
            "type": "string",
            "enum": list(string_columns),
            "description": "Optional string column to group matching rows by.",
        }

    return {"type": "object", "properties": properties}


def _load_csv_rows(file_path: Path) -> list[dict[str, str]]:
    with file_path.open(newline="", encoding="utf-8-sig") as file:
        return list(csv.DictReader(file))


def _parse_row(raw_row: Mapping[str, str | None], columns: Sequence[DatasetColumn]) -> dict[str, Any]:
    parsed: dict[str, Any] = {}
    for column in columns:
        raw_value = raw_row.get(column.name)
        text = raw_value.strip() if isinstance(raw_value, str) else ""
        if column.column_type == "number":
            parsed[column.name] = float(text.replace(",", "")) if text else 0.0
        else:
            parsed[column.name] = text
    return parsed


def _filters_argument(arguments: ToolArguments, string_columns: Sequence[str]) -> dict[str, str]:
    if not string_columns:
        return {}

    value = arguments.get("filters", {})
    if value is None:
        return {}
    if not isinstance(value, Mapping):
        raise ValueError("filters must be an object.")

    allowed = set(string_columns)
    filters: dict[str, str] = {}
    for key, filter_value in value.items():
        if key not in allowed:
            allowed_list = ", ".join(string_columns)
            raise ValueError(f"filters may only include: {allowed_list}.")
        if not isinstance(filter_value, str) or filter_value.strip() == "":
            raise ValueError(f"filters.{key} must be a non-empty string.")
        filters[key] = filter_value.strip()
    return filters


def _optional_group_by(arguments: ToolArguments, string_columns: Sequence[str]) -> str | None:
    value = arguments.get("group_by")
    if value is None:
        return None
    if value not in string_columns:
        allowed = ", ".join(string_columns)
        raise ValueError(f"group_by must be one of: {allowed}.")
    return value


def _limit_argument(arguments: ToolArguments) -> int:
    value = arguments.get("limit", 10)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("limit must be an integer.")
    if value < 1 or value > 50:
        raise ValueError("limit must be between 1 and 50.")
    return value


def _row_matches_filters(row: Mapping[str, Any], filters: Mapping[str, str]) -> bool:
    return all(str(row[key]) == value for key, value in filters.items())


def _summarize_rows(rows: Sequence[Mapping[str, Any]], numeric_columns: Sequence[str]) -> dict[str, Any]:
    summary: dict[str, Any] = {"row_count": len(rows)}
    for column in numeric_columns:
        values = [float(row[column]) for row in rows]
        summary[f"total_{column}"] = round(sum(values), 4)
        summary[f"average_{column}"] = round(sum(values) / len(values), 4) if values else 0.0
    return summary


def _group_rows(
    rows: Sequence[Mapping[str, Any]],
    group_by: str,
    numeric_columns: Sequence[str],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(str(row[group_by]), []).append(dict(row))

    groups = [
        {
            group_by: group_value,
            **_summarize_rows(group_rows, numeric_columns),
        }
        for group_value, group_rows in grouped.items()
    ]
    return sorted(groups, key=lambda group: str(group[group_by]))
