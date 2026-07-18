from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient

from app.database import get_database_connection
from app.main import app
from app.storage import connect_database, create_custom_agent


def test_agents_endpoint_returns_registry_and_empty_supervisor_team():
    response = TestClient(app).get("/agents")

    assert response.status_code == 200
    payload = response.json()

    assert payload["supervisor_agent_id"] == "supervisor"
    assert payload["supervisor_team_agent_ids"] == []
    assert [team["id"] for team in payload["teams"] if team["source"] == "builtin"] == []
    assert [agent["id"] for agent in payload["agents"] if agent["source"] == "builtin"] == [
        "supervisor"
    ]
    connector_ids = [
        agent["id"] for agent in payload["agents"] if agent["source"] == "connector"
    ]
    assert connector_ids == [
        "connector_sales_pipeline",
        "connector_account_directory",
    ]


def test_agents_endpoint_includes_custom_agent_teams(tmp_path):
    db_path = tmp_path / "chatroom.sqlite3"
    connection = connect_database(db_path)
    try:
        created = create_custom_agent(
            connection,
            name="Q4 Analyst",
            description="Looks at quarterly revenue patterns.",
            system_prompt="You are a quarterly revenue analyst.",
            tools=["lookup_account"]
        )
        connection.commit()
    finally:
        connection.close()

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        response = TestClient(app).get("/agents")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    team_ids = [team["id"] for team in payload["teams"]]

    assert "custom_agents" in team_ids
    assert f"team_{created.id}" in team_ids

    solo_team = next(team for team in payload["teams"] if team["id"] == f"team_{created.id}")
    assert solo_team == {
        "id": f"team_{created.id}",
        "name": "Q4 Analyst",
        "description": "Looks at quarterly revenue patterns.",
        "agent_ids": [created.id],
        "source": "custom",
    }


def test_agents_endpoint_serializes_supervisor_metadata():
    response = TestClient(app).get("/agents")

    supervisor = next(
        agent for agent in response.json()["agents"] if agent["id"] == "supervisor"
    )

    assert supervisor["name"] == "Supervisor Agent"
    assert supervisor["tools"] == []
    assert supervisor["source"] == "builtin"


def _override_connection(db_path: Path):
    def override_connection() -> Iterator:
        connection = connect_database(db_path)
        try:
            yield connection
        finally:
            connection.close()

    return override_connection
