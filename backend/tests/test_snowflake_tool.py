import pytest
from unittest.mock import patch

from app.connectors.snowflake import set_snowflake_executor
from app.tool_registry import list_all_tools, resolve_tool, run_registered_tool
from tests.test_snowflake_connector import FakeSnowflakeExecutor, _settings
from tools.snowflake_query import QUERY_SNOWFLAKE_TOOL, run_query_snowflake


def setup_function() -> None:
    set_snowflake_executor(None)


def test_query_snowflake_tool_is_hidden_without_credentials():
    assert resolve_tool("query_snowflake", settings=_settings(snowflake_account=None)) is None


def test_query_snowflake_tool_appears_when_configured():
    settings = _settings()
    tool_names = [tool.name for tool in list_all_tools(settings=settings)]

    assert "query_snowflake" in tool_names
    assert resolve_tool("query_snowflake", settings=settings) is QUERY_SNOWFLAKE_TOOL


@patch("app.connectors.snowflake.get_settings")
def test_run_query_snowflake_rejects_missing_configuration(mock_get_settings):
    mock_get_settings.return_value = _settings(
        snowflake_account=None,
        snowflake_user=None,
        snowflake_password=None,
        snowflake_warehouse=None,
        snowflake_database=None,
        snowflake_schema=None,
    )
    with pytest.raises(ValueError, match="Snowflake is not configured"):
        run_query_snowflake({"sql": "SELECT 1"})


@patch("app.connectors.snowflake.get_settings")
def test_run_registered_tool_executes_mocked_snowflake_query(mock_get_settings):
    settings = _settings()
    mock_get_settings.return_value = settings
    executor = FakeSnowflakeExecutor()
    set_snowflake_executor(executor)

    result = run_registered_tool(
        "query_snowflake",
        {"sql": "SELECT region FROM sales"},
        settings=settings,
    )

    assert result["rows"] == [{"region": "West", "total_revenue": 100.0}]
    assert len(executor.calls) == 1


@patch("app.connectors.snowflake.get_settings")
def test_run_query_snowflake_accepts_string_max_rows(mock_get_settings):
    settings = _settings()
    mock_get_settings.return_value = settings
    executor = FakeSnowflakeExecutor()
    set_snowflake_executor(executor)

    run_query_snowflake({"sql": "SELECT 1", "max_rows": "10"})

    assert executor.calls[0][1] == "SELECT 1 LIMIT 10"


@patch("app.connectors.snowflake.get_settings")
def test_run_query_snowflake_treats_null_max_rows_as_default(mock_get_settings):
    settings = _settings()
    mock_get_settings.return_value = settings
    executor = FakeSnowflakeExecutor()
    set_snowflake_executor(executor)

    run_query_snowflake({"sql": "SELECT 1", "max_rows": None})

    assert executor.calls[0][1] == "SELECT 1 LIMIT 100"


def test_max_rows_argument_coerces_common_provider_shapes():
    from tools.snowflake_query import _max_rows_argument

    assert _max_rows_argument({}) == 100
    assert _max_rows_argument({"max_rows": None}) == 100
    assert _max_rows_argument({"max_rows": "10"}) == 10
    assert _max_rows_argument({"max_rows": 10.0}) == 10
    assert _max_rows_argument({"max_rows": 25}) == 25

    with pytest.raises(ValueError, match="integer"):
        _max_rows_argument({"max_rows": "ten"})
    with pytest.raises(ValueError, match="between"):
        _max_rows_argument({"max_rows": "0"})
