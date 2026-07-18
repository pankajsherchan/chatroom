from pathlib import Path

import pytest

from app.connectors.external_api import (
    external_api_connector_health,
    external_api_is_configured,
    external_api_missing_settings,
    list_accounts,
    lookup_account,
    set_http_transport,
)
from app.models.external_api import validate_account_id
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
        snowflake_account=overrides.get("snowflake_account"),  # type: ignore[arg-type]
        snowflake_user=overrides.get("snowflake_user"),  # type: ignore[arg-type]
        snowflake_password=overrides.get("snowflake_password"),  # type: ignore[arg-type]
        snowflake_warehouse=overrides.get("snowflake_warehouse"),  # type: ignore[arg-type]
        snowflake_database=overrides.get("snowflake_database"),  # type: ignore[arg-type]
        snowflake_schema=overrides.get("snowflake_schema"),  # type: ignore[arg-type]
        snowflake_role=overrides.get("snowflake_role"),  # type: ignore[arg-type]
        snowflake_mock_url=overrides.get("snowflake_mock_url", "http://127.0.0.1:8011"),  # type: ignore[arg-type]
        external_api_base_url=overrides.get("external_api_base_url", "https://api.example.com"),  # type: ignore[arg-type]
        external_api_key=overrides.get("external_api_key", "secret"),  # type: ignore[arg-type]
        external_api_timeout_seconds=overrides.get("external_api_timeout_seconds", 10.0),  # type: ignore[arg-type]
        turn_reports_enabled=overrides.get("turn_reports_enabled", False),  # type: ignore[arg-type]
        turn_reports_dir=overrides.get("turn_reports_dir", Path("backend/data/turn_reports")),  # type: ignore[arg-type]
    )


class FakeHttpTransport:
    def __init__(self, payload: dict[str, object] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, str], float]] = []
        self.payload = payload or {
            "account_id": "AC-1001",
            "name": "Northwind Traders",
            "segment": "Enterprise",
            "status": "active",
        }
        self.list_payload = {
            "accounts": [
                {
                    "account_id": "AC-1001",
                    "name": "Northwind Traders",
                    "segment": "Enterprise",
                    "status": "active",
                },
                {
                    "account_id": "AC-1002",
                    "name": "Contoso Retail",
                    "segment": "Mid-Market",
                    "status": "active",
                },
            ]
        }

    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> dict[str, object]:
        self.calls.append((url, headers, timeout_seconds))
        if url.endswith("/accounts"):
            return dict(self.list_payload)
        return dict(self.payload)


class TimeoutHttpTransport:
    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> dict[str, object]:
        raise TimeoutError("timed out")


def setup_function() -> None:
    set_http_transport(None)


def test_external_api_missing_settings_lists_required_env_vars():
    settings = _settings(external_api_base_url=None)

    assert external_api_missing_settings(settings) == ["EXTERNAL_API_BASE_URL"]
    assert external_api_is_configured(settings) is False


def test_external_api_connector_health_reports_ready_when_configured():
    health = external_api_connector_health(_settings())

    assert health == {
        "id": "external_api",
        "name": "Account directory",
        "purpose": "Look up customer accounts, segments, and status.",
        "configuration_hint": (
            "Configured in the backend via .env (EXTERNAL_API_BASE_URL). "
            "Local dev uses the account API mock in mock_services/."
        ),
        "tool_name": "lookup_account",
        "ready": True,
        "missing": [],
        "message": "Ready to look up accounts.",
    }


def test_validate_account_id_rejects_empty_values():
    with pytest.raises(ValueError, match="account_id must be a non-empty string"):
        validate_account_id("   ")


def test_lookup_account_uses_injected_transport():
    transport = FakeHttpTransport()
    set_http_transport(transport)
    settings = _settings()

    result = lookup_account("AC-1001", settings=settings)

    assert result == {
        "account_id": "AC-1001",
        "name": "Northwind Traders",
        "segment": "Enterprise",
        "status": "active",
        "source": "external_api",
    }
    assert transport.calls[0][0] == "https://api.example.com/accounts/AC-1001"
    assert transport.calls[0][1]["Authorization"] == "Bearer secret"


def test_lookup_account_strips_trailing_slash_from_base_url():
    transport = FakeHttpTransport()
    set_http_transport(transport)
    settings = _settings(external_api_base_url="https://api.example.com/")

    lookup_account("AC-1001", settings=settings)

    assert transport.calls[0][0] == "https://api.example.com/accounts/AC-1001"


def test_lookup_account_rejects_incomplete_response():
    transport = FakeHttpTransport(payload={"account_id": "AC-1001"})
    set_http_transport(transport)

    with pytest.raises(ValueError, match="missing fields"):
        lookup_account("AC-1001", settings=_settings())


def test_list_accounts_uses_injected_transport():
    transport = FakeHttpTransport()
    set_http_transport(transport)
    settings = _settings()

    result = list_accounts(settings=settings)

    assert result["row_count"] == 2
    assert result["accounts"][0]["account_id"] == "AC-1001"
    assert transport.calls[0][0] == "https://api.example.com/accounts"


def test_lookup_account_wraps_transport_timeouts():
    set_http_transport(TimeoutHttpTransport())

    with pytest.raises(ValueError, match="timed out"):
        lookup_account("AC-1001", settings=_settings())
