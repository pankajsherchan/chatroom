from pathlib import Path

import pytest

from app.connectors.snowflake import (
    SnowflakeConfig,
    execute_snowflake_query,
    set_snowflake_executor,
    snowflake_connector_health,
    snowflake_is_configured,
    snowflake_missing_settings,
    validate_select_sql,
)
from app.settings import Settings


def _settings(**overrides: object) -> Settings:
    return Settings(
        model_provider="ollama",
        backend_host="127.0.0.1",
        backend_port=8001,
        frontend_api_base_url="http://127.0.0.1:8001",
        sqlite_db_path=Path("backend/data/chatroom.sqlite3"),
        artifact_static_dir=Path("backend/data/artifacts"),
        imported_datasets_dir=Path("backend/data/datasets"),
        openai_api_key=None,
        openai_model=None,
        ollama_base_url="http://localhost:11434",
        ollama_model=None,
        aws_profile=None,
        aws_region="us-east-1",
        bedrock_model_id=None,
        snowflake_account=overrides.get("snowflake_account", "acct"),  # type: ignore[arg-type]
        snowflake_user=overrides.get("snowflake_user", "user"),  # type: ignore[arg-type]
        snowflake_password=overrides.get("snowflake_password", "secret"),  # type: ignore[arg-type]
        snowflake_warehouse=overrides.get("snowflake_warehouse", "WH"),  # type: ignore[arg-type]
        snowflake_database=overrides.get("snowflake_database", "DB"),  # type: ignore[arg-type]
        snowflake_schema=overrides.get("snowflake_schema", "PUBLIC"),  # type: ignore[arg-type]
        snowflake_role=overrides.get("snowflake_role"),  # type: ignore[arg-type]
        snowflake_mock_url=overrides.get("snowflake_mock_url", "http://127.0.0.1:8011"),  # type: ignore[arg-type]
        external_api_base_url=overrides.get("external_api_base_url"),  # type: ignore[arg-type]
        external_api_key=overrides.get("external_api_key"),  # type: ignore[arg-type]
        external_api_timeout_seconds=overrides.get("external_api_timeout_seconds", 10.0),  # type: ignore[arg-type]
        turn_reports_enabled=overrides.get("turn_reports_enabled", False),  # type: ignore[arg-type]
        turn_reports_dir=overrides.get("turn_reports_dir", Path("backend/data/turn_reports")),  # type: ignore[arg-type]
    )


class FakeSnowflakeExecutor:
    def __init__(self) -> None:
        self.calls: list[tuple[SnowflakeConfig, str]] = []

    def execute(self, config: SnowflakeConfig, sql: str) -> dict[str, object]:
        self.calls.append((config, sql))
        return {
            "sql": sql,
            "columns": ["region", "total_revenue"],
            "row_count": 1,
            "rows": [{"region": "West", "total_revenue": 100.0}],
        }


def setup_function() -> None:
    set_snowflake_executor(None)


def test_snowflake_missing_settings_lists_required_env_vars():
    settings = _settings(snowflake_password=None)

    assert snowflake_missing_settings(settings) == ["SNOWFLAKE_PASSWORD"]
    assert snowflake_is_configured(settings) is False


def test_snowflake_connector_health_reports_ready_when_configured():
    health = snowflake_connector_health(_settings())

    assert health == {
        "id": "snowflake",
        "name": "Sales pipeline",
        "purpose": "Query deal stages, regions, and revenue.",
        "configuration_hint": (
            "Configured in the backend via .env (SNOWFLAKE_* settings). "
            "Local dev uses the SQL mock in mock_services/."
        ),
        "tool_name": "query_snowflake",
        "ready": True,
        "missing": [],
        "message": "Ready to query pipeline data.",
    }


def test_validate_select_sql_rejects_non_select_statements():
    with pytest.raises(ValueError, match="Only SELECT"):
        validate_select_sql("DELETE FROM sales")


def test_validate_select_sql_appends_limit_when_missing():
    assert validate_select_sql("SELECT region FROM sales") == "SELECT region FROM sales LIMIT 100"


def test_execute_snowflake_query_uses_injected_executor():
    executor = FakeSnowflakeExecutor()
    set_snowflake_executor(executor)

    result = execute_snowflake_query(
        "SELECT region, SUM(revenue) AS total_revenue FROM sales GROUP BY region",
        settings=_settings(),
        max_rows=20,
    )

    assert result["row_count"] == 1
    assert executor.calls[0][1].endswith("LIMIT 20")


def test_snowflake_connector_health_mentions_local_mock_when_configured():
    health = snowflake_connector_health(
        _settings(
            snowflake_account="local",
            snowflake_user="mock",
            snowflake_password="mock",
            snowflake_warehouse="MOCK_WH",
            snowflake_database="MOCK_DB",
            snowflake_schema="PUBLIC",
        )
    )

    assert health["ready"] is True
    assert "mock_services" in health["configuration_hint"]
    assert "pipeline" in health["message"].casefold()
