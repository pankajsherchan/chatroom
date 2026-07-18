from fastapi.testclient import TestClient

from app.main import app
from app.settings import get_settings
from tests.test_external_api_connector import _settings


def test_connectors_endpoint_reports_optional_connector_status():
    app.dependency_overrides[get_settings] = lambda: _settings(external_api_base_url=None)
    try:
        response = TestClient(app).get("/connectors")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert len(payload["connectors"]) == 2

    snowflake = next(item for item in payload["connectors"] if item["id"] == "snowflake")
    assert snowflake["name"] == "Sales pipeline"
    assert snowflake["tool_name"] == "query_snowflake"
    assert snowflake["ready"] is False
    assert "SNOWFLAKE_ACCOUNT" in snowflake["missing"]

    external_api = next(item for item in payload["connectors"] if item["id"] == "external_api")
    assert external_api["name"] == "Account directory"
    assert external_api["tool_name"] == "lookup_account"
    assert external_api["ready"] is False
    assert "EXTERNAL_API_BASE_URL" in external_api["missing"]
