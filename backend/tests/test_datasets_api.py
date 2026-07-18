from collections.abc import Iterator
from pathlib import Path

from fastapi.testclient import TestClient

from app.database import get_database_connection
from app.main import app
from app.storage import connect_database


def test_datasets_api_imports_csv_and_exposes_generated_tool(tmp_path: Path):
    db_path = tmp_path / "chatroom.sqlite3"
    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    csv_bytes = (
        "region,revenue,units\n"
        "West,100,2\n"
        "East,200,3\n"
    ).encode("utf-8")

    try:
        client = TestClient(app)
        create_response = client.post(
            "/datasets",
            data={"name": "Pipeline", "description": "Quarterly pipeline"},
            files={"file": ("pipeline.csv", csv_bytes, "text/csv")},
        )
        assert create_response.status_code == 201
        created = create_response.json()
        assert created["name"] == "Pipeline"
        assert created["tool_name"].startswith("query_dataset_")
        assert created["columns"] == [
            {"name": "region", "column_type": "string"},
            {"name": "revenue", "column_type": "number"},
            {"name": "units", "column_type": "number"},
        ]

        list_response = client.get("/datasets")
        assert list_response.status_code == 200
        assert len(list_response.json()["datasets"]) == 1

        tools_response = client.get("/tools")
        tool_names = [tool["name"] for tool in tools_response.json()["tools"]]
        assert created["tool_name"] in tool_names

        delete_response = client.delete(f"/datasets/{created['id']}")
        assert delete_response.status_code == 204
        assert client.get("/datasets").json()["datasets"] == []
    finally:
        app.dependency_overrides.clear()


def _override_connection(db_path: Path):
    def override_connection() -> Iterator:
        connection = connect_database(db_path)
        try:
            yield connection
        finally:
            connection.close()

    return override_connection
