from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from app.database import get_database_connection
from app.main import app
from app.storage import connect_database, create_custom_agent


def test_custom_agents_crud_round_trip(tmp_path):
    db_path = tmp_path / "chatroom.sqlite3"
    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        client = TestClient(app)
        create_response = client.post(
            "/custom-agents",
            json={
                "name": "Q4 Analyst",
                "description": "Looks at quarterly revenue patterns.",
                "system_prompt": "You are a quarterly revenue analyst.",
                "tools": ["lookup_account"]
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["id"].startswith("custom_")
        assert created["source"] == "custom"

        list_response = client.get("/custom-agents")
        assert list_response.status_code == 200
        assert list_response.json()[0]["id"] == created["id"]

        update_response = client.put(
            f"/custom-agents/{created['id']}",
            json={
                "name": "Q4 Revenue Analyst",
                "description": "Looks at quarterly revenue patterns.",
                "system_prompt": "You are a quarterly revenue analyst with concise answers.",
                "tools": ["lookup_account"]
            },
        )
        assert update_response.status_code == 200
        assert update_response.json()["name"] == "Q4 Revenue Analyst"
        assert update_response.json()["tools"] == ["lookup_account"]

        delete_response = client.delete(f"/custom-agents/{created['id']}")
        assert delete_response.status_code == 204
        assert client.get(f"/custom-agents/{created['id']}").status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_custom_agents_reject_unknown_tools(tmp_path):
    app.dependency_overrides[get_database_connection] = _override_connection(
        tmp_path / "chatroom.sqlite3"
    )
    try:
        response = TestClient(app).post(
            "/custom-agents",
            json={
                "name": "Broken",
                "description": "Uses an unknown tool",
                "system_prompt": "Prompt",
                "tools": ["missing_tool"]
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "Unknown tools" in response.json()["error"]["message"]


def test_agents_endpoint_includes_custom_agents(tmp_path):
    db_path = tmp_path / "chatroom.sqlite3"
    with _connect_for_assertion(db_path) as connection:
        custom = create_custom_agent(
            connection,
            name="Custom Helper",
            description="A saved custom specialist.",
            system_prompt="Help with custom analysis.",
            tools=["lookup_account"]
        )

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        response = TestClient(app).get("/agents")
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    custom_agent = next(agent for agent in payload["agents"] if agent["id"] == custom.id)
    assert custom_agent["source"] == "custom"
    assert custom_agent["name"] == "Custom Helper"


def test_create_conversation_accepts_custom_agent_ids(tmp_path):
    db_path = tmp_path / "chatroom.sqlite3"
    with _connect_for_assertion(db_path) as connection:
        custom = create_custom_agent(
            connection,
            name="Revenue Helper",
            description="Revenue specialist",
            system_prompt="Analyze revenue.",
            tools=["lookup_account"]
        )

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        response = TestClient(app).post(
            "/conversations",
            json={"selected_agent_ids": [custom.id]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["selected_agent_ids"] == [
        "supervisor",
        "connector_sales_pipeline",
        "connector_account_directory",
        custom.id,
    ]


def _override_connection(db_path: Path):
    def override_connection() -> Iterator:
        connection = connect_database(db_path)
        try:
            yield connection
        finally:
            connection.close()

    return override_connection


@contextmanager
def _connect_for_assertion(db_path: Path):
    connection = connect_database(db_path)
    try:
        yield connection
    finally:
        connection.close()
