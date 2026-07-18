"""CSV inspection helpers for imported local datasets."""

from __future__ import annotations

import csv
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


ColumnType = Literal["string", "number"]
MAX_SCHEMA_SAMPLE_ROWS = 100


@dataclass(frozen=True)
class DatasetColumn:
    name: str
    column_type: ColumnType


def inspect_csv_columns(csv_path: Path) -> list[DatasetColumn]:
    """Read a CSV header and infer column types from sample rows."""

    with csv_path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            raise ValueError("CSV must include a header row.")

        headers = [header.strip() for header in reader.fieldnames]
        if not headers or any(header == "" for header in headers):
            raise ValueError("CSV header columns must be non-empty.")
        if len(set(headers)) != len(headers):
            raise ValueError("CSV header columns must be unique.")

        sample_rows = []
        for index, row in enumerate(reader):
            sample_rows.append(row)
            if index + 1 >= MAX_SCHEMA_SAMPLE_ROWS:
                break

        if not sample_rows:
            raise ValueError("CSV must include at least one data row.")

        return [
            DatasetColumn(name=header, column_type=_infer_column_type(header, sample_rows))
            for header in headers
        ]


def columns_to_json(columns: Sequence[DatasetColumn]) -> list[dict[str, str]]:
    return [{"name": column.name, "column_type": column.column_type} for column in columns]


def columns_from_json(payload: Sequence[Mapping[str, str]]) -> list[DatasetColumn]:
    return [
        DatasetColumn(name=str(item["name"]), column_type=item["column_type"])  # type: ignore[arg-type]
        for item in payload
    ]


def _infer_column_type(column_name: str, rows: Sequence[Mapping[str, str | None]]) -> ColumnType:
    values = [row.get(column_name) for row in rows]
    non_empty = [value.strip() for value in values if isinstance(value, str) and value.strip() != ""]
    if not non_empty:
        return "string"

    for value in non_empty:
        try:
            float(value.replace(",", ""))
        except ValueError:
            return "string"

    return "number"
