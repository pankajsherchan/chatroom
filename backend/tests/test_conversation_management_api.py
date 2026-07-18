import json
import logging
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from app.database import get_database_connection
from app.main import app
from app.storage import (
    append_message,
    connect_database,
    create_conversation,
    get_conversation,
    list_messages,
)


def test_rename_conversation_updates_title(tmp_path):
    db_path = tmp_path / "chatroom.sqlite3"
    with _connect_for_assertion(db_path) as connection:
        created = create_conversation(
            connection,
            selected_agent_ids=["supervisor"],
        )

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        response = TestClient(app).patch(
            f"/conversations/{created.id}",
            json={"title": "OpenAI supervisor test"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["id"] == created.id
    assert payload["title"] == "OpenAI supervisor test"

    with _connect_for_assertion(db_path) as connection:
        stored = get_conversation(connection, created.id)
        assert stored is not None
        assert stored.title == "OpenAI supervisor test"


def test_rename_conversation_rejects_blank_title(tmp_path):
    db_path = tmp_path / "chatroom.sqlite3"
    with _connect_for_assertion(db_path) as connection:
        created = create_conversation(
            connection,
            selected_agent_ids=["supervisor"],
        )

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        response = TestClient(app).patch(
            f"/conversations/{created.id}",
            json={"title": "   "},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "bad_request",
            "message": "Conversation title cannot be empty.",
        }
    }


def test_rename_conversation_returns_404_for_missing_conversation(tmp_path):
    db_path = tmp_path / "chatroom.sqlite3"

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        response = TestClient(app).patch(
            "/conversations/missing",
            json={"title": "Ghost chat"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Conversation not found: missing",
        }
    }


def test_delete_conversation_removes_saved_chat(tmp_path):
    db_path = tmp_path / "chatroom.sqlite3"
    with _connect_for_assertion(db_path) as connection:
        created = create_conversation(
            connection,
            selected_agent_ids=["supervisor"],
        )
        append_message(
            connection,
            conversation_id=created.id,
            role="user",
            content="Delete this chat",
        )

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        client = TestClient(app)
        response = client.delete(f"/conversations/{created.id}")
        detail_response = client.get(f"/conversations/{created.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""
    assert detail_response.status_code == 404

    with _connect_for_assertion(db_path) as connection:
        assert get_conversation(connection, created.id) is None
        assert list_messages(connection, created.id) == []


def test_delete_conversation_returns_404_for_missing_conversation(tmp_path):
    db_path = tmp_path / "chatroom.sqlite3"

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        response = TestClient(app).delete("/conversations/missing")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Conversation not found: missing",
        }
    }


def test_stream_message_returns_request_id_header(tmp_path, caplog):
    db_path = tmp_path / "chatroom.sqlite3"
    with _connect_for_assertion(db_path) as connection:
        created = create_conversation(
            connection,
            selected_agent_ids=["supervisor"],
        )

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        with caplog.at_level(logging.INFO, logger="chatroom"):
            response = TestClient(app).post(
                f"/conversations/{created.id}/messages/stream",
                json={"content": "What was revenue by region?"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    request_id = response.headers.get("x-request-id")
    assert request_id
    assert len(request_id) == 36

    logged_events = [json.loads(record.message) for record in caplog.records]
    started = next(
        event for event in logged_events if event["event"] == "chat_request_started"
    )
    finished = next(
        event for event in logged_events if event["event"] == "chat_request_finished"
    )
    supervisor_started = next(
        event for event in logged_events if event["event"] == "supervisor_started"
    )
    supervisor_finished = next(
        event for event in logged_events if event["event"] == "supervisor_finished"
    )

    assert started["request_id"] == request_id
    assert finished["request_id"] == request_id
    assert finished["status"] == "success"
    assert finished["duration_ms"] >= 0
    assert supervisor_started["request_id"] == request_id
    assert supervisor_finished["request_id"] == request_id
    assert supervisor_finished["duration_ms"] >= 0


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
