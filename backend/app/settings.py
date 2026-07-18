"""Runtime settings for the ChatRoom backend."""

import os
from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SUPPORTED_MODEL_PROVIDERS = {"openai", "ollama", "bedrock"}
UI_MODEL_PROVIDERS = ("ollama", "openai", "bedrock")

_model_provider_override: str | None = None


@dataclass(frozen=True)
class Settings:
    """Configuration loaded from environment variables."""

    model_provider: str
    backend_host: str
    backend_port: int
    frontend_api_base_url: str
    sqlite_db_path: Path
    artifact_static_dir: Path
    imported_datasets_dir: Path
    openai_api_key: str | None
    openai_model: str | None
    ollama_base_url: str
    ollama_model: str | None
    aws_profile: str | None
    aws_region: str
    bedrock_model_id: str | None
    snowflake_account: str | None
    snowflake_user: str | None
    snowflake_password: str | None
    snowflake_warehouse: str | None
    snowflake_database: str | None
    snowflake_schema: str | None
    snowflake_role: str | None
    snowflake_mock_url: str
    external_api_base_url: str | None
    external_api_key: str | None
    external_api_timeout_seconds: float
    turn_reports_enabled: bool
    turn_reports_dir: Path

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "Settings":
        model_provider = _env_str(env, "MODEL_PROVIDER", "ollama").lower()
        if model_provider not in SUPPORTED_MODEL_PROVIDERS:
            providers = ", ".join(sorted(SUPPORTED_MODEL_PROVIDERS))
            raise ValueError(
                f"Unsupported MODEL_PROVIDER={model_provider!r}. "
                f"Expected one of: {providers}."
            )

        return cls(
            model_provider=model_provider,
            backend_host=_env_str(env, "BACKEND_HOST", "127.0.0.1"),
            backend_port=_env_int(env, "BACKEND_PORT", 8001),
            frontend_api_base_url=_env_str(
                env,
                "FRONTEND_API_BASE_URL",
                "http://127.0.0.1:8001",
            ),
            sqlite_db_path=_env_path(
                env,
                "SQLITE_DB_PATH",
                "backend/data/chatroom.sqlite3",
            ),
            artifact_static_dir=_env_path(
                env,
                "ARTIFACT_STATIC_DIR",
                "backend/data/artifacts",
            ),
            imported_datasets_dir=_env_path(
                env,
                "IMPORTED_DATASETS_DIR",
                "backend/data/datasets",
            ),
            openai_api_key=_env_optional(env, "OPENAI_API_KEY"),
            openai_model=_env_optional(env, "OPENAI_MODEL"),
            ollama_base_url=_env_str(
                env,
                "OLLAMA_BASE_URL",
                "http://localhost:11434",
            ),
            ollama_model=_env_optional(env, "OLLAMA_MODEL"),
            aws_profile=_env_optional(env, "AWS_PROFILE"),
            aws_region=_env_str(env, "AWS_REGION", "us-east-1"),
            bedrock_model_id=_env_optional(env, "BEDROCK_MODEL_ID"),
            snowflake_account=_env_optional(env, "SNOWFLAKE_ACCOUNT"),
            snowflake_user=_env_optional(env, "SNOWFLAKE_USER"),
            snowflake_password=_env_optional(env, "SNOWFLAKE_PASSWORD"),
            snowflake_warehouse=_env_optional(env, "SNOWFLAKE_WAREHOUSE"),
            snowflake_database=_env_optional(env, "SNOWFLAKE_DATABASE"),
            snowflake_schema=_env_optional(env, "SNOWFLAKE_SCHEMA"),
            snowflake_role=_env_optional(env, "SNOWFLAKE_ROLE"),
            snowflake_mock_url=_env_str(
                env,
                "SNOWFLAKE_MOCK_URL",
                "http://127.0.0.1:8011",
            ),
            external_api_base_url=_env_optional(env, "EXTERNAL_API_BASE_URL"),
            external_api_key=_env_optional(env, "EXTERNAL_API_KEY"),
            external_api_timeout_seconds=float(
                _env_int(env, "EXTERNAL_API_TIMEOUT_SECONDS", 10)
            ),
            turn_reports_enabled=_env_bool(env, "TURN_REPORTS_ENABLED", False),
            turn_reports_dir=_env_path(
                env,
                "TURN_REPORTS_DIR",
                "backend/data/turn_reports",
            ),
        )


@lru_cache
def get_settings() -> Settings:
    """Load settings once per process."""

    load_dotenv(PROJECT_ROOT / ".env", override=False)
    return Settings.from_env(os.environ)


def get_active_model_provider(settings: Settings | None = None) -> str:
    """Return the runtime-selected provider, falling back to env default."""

    settings = settings or get_settings()
    if _model_provider_override is not None:
        return _model_provider_override
    return settings.model_provider


def set_active_model_provider(provider_id: str) -> str:
    """Switch the active model provider for this backend process."""

    normalized = provider_id.strip().lower()
    if normalized not in UI_MODEL_PROVIDERS:
        allowed = ", ".join(UI_MODEL_PROVIDERS)
        raise ValueError(
            f"Unsupported provider_id={provider_id!r}. Expected one of: {allowed}."
        )

    global _model_provider_override
    _model_provider_override = normalized
    return normalized


def clear_active_model_provider() -> None:
    """Clear any runtime provider override."""

    global _model_provider_override
    _model_provider_override = None


def effective_settings(settings: Settings | None = None) -> Settings:
    """Return settings with the runtime provider override applied."""

    settings = settings or get_settings()
    active_provider = get_active_model_provider(settings)
    if active_provider == settings.model_provider:
        return settings
    return replace(settings, model_provider=active_provider)


def _env_optional(env: Mapping[str, str], key: str) -> str | None:
    value = env.get(key)
    if value is None or value.strip() == "":
        return None
    return value.strip()


def _env_str(env: Mapping[str, str], key: str, default: str) -> str:
    return _env_optional(env, key) or default


def _env_bool(env: Mapping[str, str], key: str, default: bool) -> bool:
    value = _env_optional(env, key)
    if value is None:
        return default
    return value.casefold() not in {"0", "false", "no", "off"}


def _env_int(env: Mapping[str, str], key: str, default: int) -> int:
    value = _env_optional(env, key)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError as error:
        raise ValueError(f"{key} must be an integer, got {value!r}.") from error


def _env_path(env: Mapping[str, str], key: str, default: str) -> Path:
    path = Path(_env_str(env, key, default)).expanduser()
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path