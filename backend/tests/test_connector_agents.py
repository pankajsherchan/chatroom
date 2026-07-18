from app.connector_agents import (
    CONNECTOR_ACCOUNT_DIRECTORY_ID,
    CONNECTOR_SALES_PIPELINE_ID,
    list_connector_agent_ids,
    list_connector_agents,
)
from app.settings import get_settings
from tests.test_external_api_connector import _settings as external_api_settings


def test_list_connector_agents_includes_configured_connectors():
    settings = external_api_settings(
        external_api_base_url="https://api.example.com",
        snowflake_account="local",
        snowflake_user="mock",
        snowflake_password="mock",
        snowflake_warehouse="MOCK_WH",
        snowflake_database="MOCK_DB",
        snowflake_schema="PUBLIC",
    )

    agents = list_connector_agents(settings)

    assert [agent.id for agent in agents] == [
        CONNECTOR_SALES_PIPELINE_ID,
        CONNECTOR_ACCOUNT_DIRECTORY_ID,
    ]
    assert agents[0].tools == ("query_snowflake",)
    assert agents[1].tools == ("lookup_account",)


def test_list_connector_agents_omits_unconfigured_connectors():
    settings = external_api_settings(external_api_base_url=None)

    assert list_connector_agents(settings) == []
    assert list_connector_agent_ids(settings) == []


def test_agents_endpoint_includes_connector_agents():
    from fastapi.testclient import TestClient

    from app.main import app

    response = TestClient(app).get("/agents")
    payload = response.json()

    connector_agents = [
        agent for agent in payload["agents"] if agent["source"] == "connector"
    ]
    assert [agent["id"] for agent in connector_agents] == list_connector_agent_ids(
        get_settings()
    )
