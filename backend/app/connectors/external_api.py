"""Optional external HTTP API connector for local development."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from app.models.external_api import validate_account_id
from app.settings import Settings, get_settings


class HttpTransport(Protocol):
    def get_json(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout_seconds: float,
    ) -> dict[str, object]:
        """Fetch one JSON object from an HTTP GET endpoint."""


@dataclass(frozen=True)
class ExternalApiConfig:
    base_url: str
    api_key: str | None
    timeout_seconds: float


_transport: HttpTransport | None = None


def set_http_transport(transport: HttpTransport | None) -> None:
    global _transport
    _transport = transport


def external_api_missing_settings(settings: Settings) -> list[str]:
    missing: list[str] = []
    if not settings.external_api_base_url:
        missing.append("EXTERNAL_API_BASE_URL")
    return missing


def external_api_is_configured(settings: Settings | None = None) -> bool:
    settings = settings or get_settings()
    return not external_api_missing_settings(settings)


def external_api_config_from_settings(settings: Settings) -> ExternalApiConfig | None:
    if not settings.external_api_base_url:
        return None

    return ExternalApiConfig(
        base_url=settings.external_api_base_url.rstrip("/"),
        api_key=settings.external_api_key,
        timeout_seconds=settings.external_api_timeout_seconds,
    )


def external_api_connector_health(settings: Settings | None = None) -> dict[str, object]:
    settings = settings or get_settings()
    missing = external_api_missing_settings(settings)
    ready = not missing
    return {
        "id": "external_api",
        "name": "Account directory",
        "purpose": "Look up customer accounts, segments, and status.",
        "configuration_hint": (
            "Configured in the backend via .env (EXTERNAL_API_BASE_URL). "
            "Local dev uses the account API mock in mock_services/."
        ),
        "tool_name": "lookup_account",
        "ready": ready,
        "missing": missing,
        "message": (
            "Ready to look up accounts."
            if ready
            else f"Missing: {', '.join(missing)}"
        ),
    }


def lookup_account(
    account_id: str,
    *,
    settings: Settings | None = None,
) -> dict[str, object]:
    settings = settings or get_settings()
    config = external_api_config_from_settings(settings)
    if config is None:
        missing = ", ".join(external_api_missing_settings(settings))
        raise ValueError(f"External API is not configured. Missing: {missing}")

    safe_id = validate_account_id(account_id)
    url = f"{config.base_url}/accounts/{safe_id}"
    payload = _get_json(config, url)
    return _parse_account_response(payload)


def list_accounts(*, settings: Settings | None = None) -> dict[str, object]:
    settings = settings or get_settings()
    config = external_api_config_from_settings(settings)
    if config is None:
        missing = ", ".join(external_api_missing_settings(settings))
        raise ValueError(f"External API is not configured. Missing: {missing}")

    url = f"{config.base_url}/accounts"
    payload = _get_json(config, url)
    return _parse_accounts_list_response(payload)


def _get_json(config: ExternalApiConfig, url: str) -> dict[str, object]:
    headers: dict[str, str] = {}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"

    if _transport is not None:
        try:
            return _transport.get_json(
                url,
                headers=headers,
                timeout_seconds=config.timeout_seconds,
            )
        except TimeoutError as error:
            raise ValueError(
                f"External API request timed out after {config.timeout_seconds} seconds."
            ) from error

    return _default_get_json(
        url,
        headers=headers,
        timeout_seconds=config.timeout_seconds,
    )


def _default_get_json(
    url: str,
    headers: dict[str, str],
    timeout_seconds: float,
) -> dict[str, object]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except TimeoutError as error:
        raise ValueError(
            f"External API request timed out after {timeout_seconds} seconds."
        ) from error
    except urllib.error.HTTPError as error:
        raise ValueError(f"External API returned HTTP {error.code}.") from error
    except urllib.error.URLError as error:
        raise ValueError(f"External API request failed: {error.reason}.") from error
    except json.JSONDecodeError as error:
        raise ValueError("External API response was not valid JSON.") from error

    if not isinstance(payload, dict):
        raise ValueError("External API response must be a JSON object.")
    return payload


def _parse_account_response(payload: dict[str, object]) -> dict[str, object]:
    required = ("account_id", "name", "segment", "status")
    missing = [field for field in required if field not in payload]
    if missing:
        raise ValueError(
            f"External API response missing fields: {', '.join(missing)}"
        )

    return {
        "account_id": str(payload["account_id"]),
        "name": str(payload["name"]),
        "segment": str(payload["segment"]),
        "status": str(payload["status"]),
        "source": "external_api",
    }


def _parse_accounts_list_response(payload: dict[str, object]) -> dict[str, object]:
    accounts_raw = payload.get("accounts")
    if not isinstance(accounts_raw, list):
        raise ValueError("External API response must include an accounts list.")

    accounts: list[dict[str, str]] = []
    for item in accounts_raw:
        if not isinstance(item, dict):
            raise ValueError("Each account in the accounts list must be an object.")
        parsed = _parse_account_response(item)
        accounts.append(
            {
                "account_id": str(parsed["account_id"]),
                "name": str(parsed["name"]),
                "segment": str(parsed["segment"]),
                "status": str(parsed["status"]),
            }
        )

    return {
        "accounts": accounts,
        "row_count": len(accounts),
        "source": "external_api",
    }
