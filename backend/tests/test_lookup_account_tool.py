from unittest.mock import patch

import pytest

from app.connectors.external_api import set_http_transport
from app.tool_registry import list_all_tools, resolve_tool, run_registered_tool
from tests.test_external_api_connector import FakeHttpTransport, _settings
from tools.lookup_account import LOOKUP_ACCOUNT_TOOL, run_lookup_account


def setup_function() -> None:
    set_http_transport(None)


def test_lookup_account_tool_is_hidden_without_configuration():
    assert resolve_tool("lookup_account", settings=_settings(external_api_base_url=None)) is None


def test_lookup_account_tool_appears_when_configured():
    settings = _settings()
    tool_names = [tool.name for tool in list_all_tools(settings=settings)]

    assert "lookup_account" in tool_names
    assert resolve_tool("lookup_account", settings=settings) is LOOKUP_ACCOUNT_TOOL


@patch("app.connectors.external_api.get_settings")
def test_run_lookup_account_rejects_missing_configuration(mock_get_settings):
    mock_get_settings.return_value = _settings(external_api_base_url=None)
    with pytest.raises(ValueError, match="External API is not configured"):
        run_lookup_account({"account_id": "AC-1001"})


@patch("app.connectors.external_api.get_settings")
def test_run_lookup_account_lists_all_accounts_when_id_omitted(mock_get_settings):
    settings = _settings()
    mock_get_settings.return_value = settings
    set_http_transport(FakeHttpTransport())

    result = run_lookup_account({})

    assert result["row_count"] == 2
    assert len(result["accounts"]) == 2


@patch("app.connectors.external_api.get_settings")
def test_run_registered_tool_executes_mocked_lookup_account(mock_get_settings):
    settings = _settings()
    mock_get_settings.return_value = settings
    transport = FakeHttpTransport()
    set_http_transport(transport)

    result = run_registered_tool(
        "lookup_account",
        {"account_id": "AC-1001"},
        settings=settings,
    )

    assert result["name"] == "Northwind Traders"
    assert len(transport.calls) == 1
