"""SQLite-backed mock Snowflake SQL endpoint for local development."""

from __future__ import annotations

import csv
import os
import sqlite3
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = (
    PROJECT_ROOT / "mock_services" / "snowflake_mock" / "data" / "pipeline_deals.csv"
)
PORT = int(os.environ.get("MOCK_SNOWFLAKE_PORT", "8011"))

app = FastAPI(title="Mock Snowflake SQL API", version="0.1.0")

_connection: sqlite3.Connection | None = None
_table_name: str | None = None


def _table_name_for_csv(csv_path: Path) -> str:
    override = os.environ.get("MOCK_SNOWFLAKE_TABLE", "").strip()
    if override:
        return override
    stem = csv_path.stem
    sanitized = "".join(char if char.isalnum() or char == "_" else "_" for char in stem)
    return sanitized or "dataset"


def _load_csv_table(connection: sqlite3.Connection, csv_path: Path) -> str:
    table_name = _table_name_for_csv(csv_path)
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = reader.fieldnames or []
        if not columns:
            raise RuntimeError(f"CSV has no header row: {csv_path}")

        quoted_columns = ", ".join(f'"{column}"' for column in columns)
        column_defs = ", ".join(f'"{column}" TEXT' for column in columns)
        connection.execute(f'CREATE TABLE "{table_name}" ({column_defs})')
        placeholders = ", ".join("?" for _ in columns)
        insert_sql = (
            f'INSERT INTO "{table_name}" ({quoted_columns}) VALUES ({placeholders})'
        )
        for row in reader:
            connection.execute(insert_sql, [row[column] for column in columns])
    return table_name


class QueryRequest(BaseModel):
    sql: str = Field(min_length=1)
    database: str | None = None
    schema_name: str | None = Field(default=None, alias="schema")
    warehouse: str | None = None

    model_config = {"populate_by_name": True}


def _connection_db() -> sqlite3.Connection:
    global _connection, _table_name
    if _connection is None:
        csv_path = Path(os.environ.get("MOCK_SNOWFLAKE_CSV", str(DEFAULT_CSV)))
        if not csv_path.exists():
            raise RuntimeError(f"Snowflake mock CSV not found: {csv_path}")

        _connection = sqlite3.connect(":memory:")
        _connection.row_factory = sqlite3.Row
        _table_name = _load_csv_table(_connection, csv_path)
        _connection.commit()
    return _connection


def _validate_select_sql(sql: str) -> str:
    cleaned = sql.strip().rstrip(";").strip()
    lowered = cleaned.casefold()
    if not lowered.startswith("select"):
        raise HTTPException(status_code=400, detail="Only SELECT statements are allowed.")
    if ";" in cleaned:
        raise HTTPException(status_code=400, detail="Only one SQL statement is allowed.")
    blocked = (" insert ", " update ", " delete ", " drop ", " create ", " alter ", " merge ")
    padded = f" {lowered} "
    for token in blocked:
        if token in padded:
            raise HTTPException(status_code=400, detail="Only read-only SELECT statements are allowed.")
    return cleaned


def _normalize_value(value: object) -> object:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


@app.get("/health")
def health() -> dict[str, str]:
    connection = _connection_db()
    table_name = _table_name or "dataset"
    row_count = connection.execute(f'SELECT COUNT(*) AS count FROM "{table_name}"').fetchone()
    count = row_count["count"] if row_count is not None else 0
    return {
        "status": "ok",
        "service": "mock_snowflake",
        "table": table_name,
        "row_count": str(count),
    }


@app.post("/query")
def query(request: QueryRequest) -> dict[str, object]:
    safe_sql = _validate_select_sql(request.sql)
    connection = _connection_db()
    try:
        cursor = connection.execute(safe_sql)
        rows = cursor.fetchall()
        columns = [description[0] for description in cursor.description or []]
    except sqlite3.Error as error:
        raise HTTPException(status_code=400, detail=f"SQL error: {error}") from error

    normalized_rows = [
        {
            column: _normalize_value(row[column])
            for column in columns
        }
        for row in rows
    ]
    return {
        "sql": safe_sql,
        "columns": columns,
        "row_count": len(normalized_rows),
        "rows": normalized_rows,
        "database": request.database,
        "schema": request.schema_name,
        "warehouse": request.warehouse,
    }


@app.get("/tables")
def tables() -> dict[str, object]:
    connection = _connection_db()
    table_rows = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name"
    ).fetchall()
    return {"tables": [row["name"] for row in table_rows]}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=PORT)
