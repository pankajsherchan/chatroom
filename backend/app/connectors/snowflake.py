"""Optional Snowflake SQL connector for local development."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from app.settings import Settings, get_settings

LOCAL_SNOWFLAKE_ACCOUNT = "local"


class SnowflakeExecutor(Protocol):
    def execute(self, config: "SnowflakeConfig", sql: str) -> dict[str, Any]:
        """Run one validated SQL statement and return tabular results."""


@dataclass(frozen=True)
class SnowflakeConfig:
    account: str
    user: str
    password: str
    warehouse: str
    database: str
    schema: str
    role: str | None = None


_executor: SnowflakeExecutor | None = None


def set_snowflake_executor(executor: SnowflakeExecutor | None) -> None:
    global _executor
    _executor = executor


def snowflake_config_from_settings(settings: Settings) -> SnowflakeConfig | None:
    missing = snowflake_missing_settings(settings)
    if missing:
        return None

    return SnowflakeConfig(
        account=settings.snowflake_account or "",
        user=settings.snowflake_user or "",
        password=settings.snowflake_password or "",
        warehouse=settings.snowflake_warehouse or "",
        database=settings.snowflake_database or "",
        schema=settings.snowflake_schema or "",
        role=settings.snowflake_role,
    )


def snowflake_missing_settings(settings: Settings) -> list[str]:
    missing: list[str] = []
    if not settings.snowflake_account:
        missing.append("SNOWFLAKE_ACCOUNT")
    if not settings.snowflake_user:
        missing.append("SNOWFLAKE_USER")
    if not settings.snowflake_password:
        missing.append("SNOWFLAKE_PASSWORD")
    if not settings.snowflake_warehouse:
        missing.append("SNOWFLAKE_WAREHOUSE")
    if not settings.snowflake_database:
        missing.append("SNOWFLAKE_DATABASE")
    if not settings.snowflake_schema:
        missing.append("SNOWFLAKE_SCHEMA")
    return missing


def snowflake_is_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return not snowflake_missing_settings(settings)


def snowflake_uses_local_mock(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    account = (settings.snowflake_account or "").strip().casefold()
    return account == LOCAL_SNOWFLAKE_ACCOUNT


def snowflake_connector_health(settings: Settings | None = None) -> dict[str, object]:
    settings = settings or get_settings()
    missing = snowflake_missing_settings(settings)
    ready = not missing
    if ready and snowflake_uses_local_mock(settings):
        message = "Ready to query pipeline deals and revenue."
    elif ready:
        message = "Ready to query pipeline data."
    else:
        message = f"Missing: {', '.join(missing)}"
    return {
        "id": "snowflake",
        "name": "Sales pipeline",
        "purpose": "Query deal stages, regions, and revenue.",
        "configuration_hint": (
            "Configured in the backend via .env (SNOWFLAKE_* settings). "
            "Local dev uses the SQL mock in mock_services/."
        ),
        "tool_name": "query_snowflake",
        "ready": ready,
        "missing": missing,
        "message": message,
    }


def validate_select_sql(sql: str, *, max_rows: int = 100) -> str:
    cleaned = sql.strip().rstrip(";").strip()
    if cleaned == "":
        raise ValueError("sql must be a non-empty SELECT statement.")

    lowered = cleaned.casefold()
    if not lowered.startswith("select"):
        raise ValueError("Only SELECT statements are allowed for the Snowflake tool.")

    blocked = (";", " insert ", " update ", " delete ", " drop ", " create ", " alter ", " merge ")
    padded = f" {lowered} "
    for token in blocked:
        if token in padded:
            raise ValueError("Only a single read-only SELECT statement is allowed.")

    if " limit " not in padded:
        cleaned = f"{cleaned} LIMIT {max_rows}"

    return cleaned


def execute_snowflake_query(
    sql: str,
    *,
    settings: Settings | None = None,
    max_rows: int = 100,
) -> dict[str, Any]:
    settings = settings or get_settings()
    config = snowflake_config_from_settings(settings)
    if config is None:
        missing = ", ".join(snowflake_missing_settings(settings))
        raise ValueError(f"Snowflake is not configured. Missing: {missing}")

    safe_sql = validate_select_sql(sql, max_rows=max_rows)
    if _executor is not None:
        return _executor.execute(config, safe_sql)
    return _default_execute(config, safe_sql)


def _default_execute(config: SnowflakeConfig, sql: str) -> dict[str, Any]:
    if config.account.strip().casefold() == LOCAL_SNOWFLAKE_ACCOUNT:
        settings = get_settings()
        return _execute_local_mock(settings, config, sql)

    try:
        import snowflake.connector
    except ImportError as error:
        raise ValueError(
            "Snowflake connector package is not installed. "
            "Run `uv sync --group snowflake` to enable live queries."
        ) from error

    connection_kwargs: dict[str, str] = {
        "account": config.account,
        "user": config.user,
        "password": config.password,
        "warehouse": config.warehouse,
        "database": config.database,
        "schema": config.schema,
    }
    if config.role:
        connection_kwargs["role"] = config.role

    connection = snowflake.connector.connect(**connection_kwargs)
    try:
        cursor = connection.cursor()
        try:
            cursor.execute(sql)
            columns = [column[0] for column in cursor.description or []]
            raw_rows = cursor.fetchall()
        finally:
            cursor.close()
    finally:
        connection.close()

    rows = [_row_to_dict(columns, row) for row in raw_rows]
    return {
        "sql": sql,
        "columns": columns,
        "row_count": len(rows),
        "rows": rows,
    }


def _execute_local_mock(
    settings: Settings,
    config: SnowflakeConfig,
    sql: str,
) -> dict[str, Any]:
    url = f"{settings.snowflake_mock_url.rstrip('/')}/query"
    payload = json.dumps(
        {
            "sql": sql,
            "database": config.database,
            "schema": config.schema,
            "warehouse": config.warehouse,
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=10.0) as response:
            body = json.loads(response.read().decode("utf-8"))
    except TimeoutError as error:
        raise ValueError(
            f"Local Snowflake mock timed out at {url}. "
            "Start it with ./mock_services/start_snowflake_mock.sh."
        ) from error
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise ValueError(
            f"Local Snowflake mock returned HTTP {error.code}: {detail}"
        ) from error
    except urllib.error.URLError as error:
        raise ValueError(
            f"Local Snowflake mock is unavailable at {url}. "
            "Start it with ./mock_services/start_snowflake_mock.sh."
        ) from error
    except json.JSONDecodeError as error:
        raise ValueError("Local Snowflake mock returned invalid JSON.") from error

    if not isinstance(body, dict):
        raise ValueError("Local Snowflake mock returned an unexpected payload.")

    return {
        "sql": str(body.get("sql", sql)),
        "columns": list(body.get("columns", [])),
        "row_count": int(body.get("row_count", 0)),
        "rows": list(body.get("rows", [])),
    }


def _row_to_dict(columns: list[str], row: tuple[Any, ...]) -> dict[str, Any]:
    return {
        column: _normalize_cell(value)
        for column, value in zip(columns, row, strict=True)
    }


def _normalize_cell(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
