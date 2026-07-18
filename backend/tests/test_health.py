from fastapi.testclient import TestClient

from app.main import app
from app.settings import get_settings


def test_health_returns_ollama_provider_by_default(monkeypatch):
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    get_settings.cache_clear()

    response = TestClient(app).get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy", "model_provider": "ollama"}

    get_settings.cache_clear()
