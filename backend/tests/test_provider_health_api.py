from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.settings import clear_active_model_provider, get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    clear_active_model_provider()
    yield
    get_settings.cache_clear()
    clear_active_model_provider()


def _provider(payload: dict, provider_id: str) -> dict:
    return next(provider for provider in payload["providers"] if provider["id"] == provider_id)


def test_providers_health_lists_ui_providers(monkeypatch):
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)

    response = TestClient(app).get("/providers/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_provider"] == "ollama"
    provider_ids = {provider["id"] for provider in payload["providers"]}
    assert provider_ids == {"ollama", "openai", "bedrock"}


def test_providers_health_reports_missing_openai_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = TestClient(app).get("/providers/health")
    payload = response.json()

    openai = _provider(payload, "openai")
    assert openai["ready"] is False
    assert openai["missing"] == ["OPENAI_API_KEY"]


def test_providers_health_reports_missing_ollama_model(monkeypatch):
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)

    response = TestClient(app).get("/providers/health")
    payload = response.json()

    ollama = _provider(payload, "ollama")
    assert ollama["ready"] is False
    assert ollama["missing"] == ["OLLAMA_MODEL"]


def test_providers_health_reports_missing_bedrock_model_id(monkeypatch):
    monkeypatch.delenv("BEDROCK_MODEL_ID", raising=False)

    response = TestClient(app).get("/providers/health")
    payload = response.json()

    bedrock = _provider(payload, "bedrock")
    assert bedrock["ready"] is False
    assert bedrock["missing"] == ["BEDROCK_MODEL_ID"]


def test_providers_health_reports_active_provider(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")

    response = TestClient(app).get("/providers/health")

    assert response.status_code == 200
    assert response.json()["active_provider"] == "ollama"


def test_providers_health_rejects_unsupported_provider(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "wat")

    response = TestClient(app, raise_server_exceptions=False).get("/providers/health")

    assert response.status_code == 500
    assert "Unsupported MODEL_PROVIDER" in response.text


def test_providers_health_live_check_runs_only_when_requested(monkeypatch):
    calls = []

    def fake_live_check(settings):
        calls.append(settings.model_provider)
        return "Fake live check succeeded."

    monkeypatch.setattr("app.providers.health.check_active_provider_live", fake_live_check)

    response = TestClient(app).get("/providers/health")

    assert response.status_code == 200
    assert calls == []


def test_providers_health_live_check_reports_active_provider_success(monkeypatch):
    calls = []

    def fake_live_check(settings):
        calls.append(settings.model_provider)
        return "Fake live check succeeded."

    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")
    monkeypatch.setattr("app.providers.health.check_active_provider_live", fake_live_check)

    response = TestClient(app).get("/providers/health?live=true")
    payload = response.json()

    ollama = _provider(payload, "ollama")
    openai = _provider(payload, "openai")
    assert response.status_code == 200
    assert calls == ["ollama"]
    assert ollama["live_checked"] is True
    assert ollama["live_ready"] is True
    assert ollama["live_message"] == "Fake live check succeeded."
    assert openai["live_checked"] is False


def test_providers_health_live_check_reports_active_provider_failure(monkeypatch):
    def fake_live_check(_settings):
        raise RuntimeError("Provider unavailable.")

    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")
    monkeypatch.setattr("app.providers.health.check_active_provider_live", fake_live_check)

    response = TestClient(app).get("/providers/health?live=true")
    payload = response.json()

    ollama = _provider(payload, "ollama")
    assert response.status_code == 200
    assert ollama["live_checked"] is True
    assert ollama["live_ready"] is False
    assert ollama["live_message"] == "Provider unavailable."


def test_set_active_provider_switches_runtime_provider(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    client = TestClient(app)
    response = client.put("/providers/active", json={"provider_id": "ollama"})

    assert response.status_code == 200
    assert response.json()["active_provider"] == "ollama"
    assert client.get("/health").json()["model_provider"] == "ollama"


def test_set_active_provider_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_MODEL", "llama3.2")

    response = TestClient(app).put("/providers/active", json={"provider_id": "mock"})

    assert response.status_code == 400
    assert "Unsupported provider_id" in response.json()["error"]["message"]


def test_set_active_provider_rejects_unsupported_provider():
    response = TestClient(app).put("/providers/active", json={"provider_id": "invalid"})

    assert response.status_code == 400
    assert "Unsupported provider_id" in response.json()["error"]["message"]


def test_providers_health_live_check_skips_unconfigured_active_provider(monkeypatch):
    monkeypatch.setenv("MODEL_PROVIDER", "openai")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    response = TestClient(app).get("/providers/health?live=true")
    payload = response.json()

    openai = _provider(payload, "openai")
    assert response.status_code == 200
    assert openai["ready"] is False
    assert openai["live_checked"] is False
    assert openai["live_ready"] is None
    assert openai["live_message"] == "Live check skipped because provider is not configured."
