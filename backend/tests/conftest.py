import sqlite3
from collections.abc import Iterator

import pytest

import app.settings
from app.settings import clear_active_model_provider, get_settings
from app.storage import connect_database


@pytest.fixture(autouse=True)
def isolated_settings_env(monkeypatch):
    """Keep tests independent from the developer's local .env file."""

    monkeypatch.setattr(app.settings, "load_dotenv", lambda *args, **kwargs: False)
    for key in (
        "MODEL_PROVIDER",
        "OPENAI_API_KEY",
        "OPENAI_MODEL",
        "OLLAMA_BASE_URL",
        "OLLAMA_MODEL",
        "AWS_PROFILE",
        "AWS_REGION",
        "BEDROCK_MODEL_ID",
    ):
        monkeypatch.delenv(key, raising=False)

    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")
    monkeypatch.setenv("EXTERNAL_API_BASE_URL", "https://api.example.com")
    monkeypatch.setenv("EXTERNAL_API_KEY", "secret")
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "local")
    monkeypatch.setenv("SNOWFLAKE_USER", "mock")
    monkeypatch.setenv("SNOWFLAKE_PASSWORD", "mock")
    monkeypatch.setenv("SNOWFLAKE_WAREHOUSE", "MOCK_WH")
    monkeypatch.setenv("SNOWFLAKE_DATABASE", "MOCK_DB")
    monkeypatch.setenv("SNOWFLAKE_SCHEMA", "PUBLIC")
    # Keep pytest from writing chat turn HTML reports into the repo data dir.
    monkeypatch.setenv("TURN_REPORTS_ENABLED", "0")

    get_settings.cache_clear()
    clear_active_model_provider()
    yield
    get_settings.cache_clear()
    clear_active_model_provider()


@pytest.fixture
def storage_connection(tmp_path) -> Iterator[sqlite3.Connection]:
    connection = connect_database(tmp_path / "chatroom.sqlite3")
    try:
        yield connection
    finally:
        connection.close()
