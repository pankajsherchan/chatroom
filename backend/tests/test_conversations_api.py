import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from app.database import get_database_connection
from app.main import app
from app.providers import ModelMessage, ModelResponse, ToolCall
from app.storage import (
    append_artifact,
    append_group_chat_event,
    append_message,
    connect_database,
    create_conversation,
    create_custom_agent,
    get_conversation,
    list_artifacts,
    list_group_chat_events,
    list_messages,
    list_tool_traces,
)
from unittest.mock import patch

from app.connectors.external_api import set_http_transport
from app.connectors.snowflake import set_snowflake_executor
from tests.test_external_api_connector import FakeHttpTransport, _settings as _external_api_settings
from tests.test_snowflake_connector import _settings as _snowflake_settings


def _local_snowflake_settings():
    return _snowflake_settings(
        snowflake_account="local",
        snowflake_user="mock",
        snowflake_password="mock",
        snowflake_warehouse="MOCK_WH",
        snowflake_database="MOCK_DB",
        snowflake_schema="PUBLIC",
    )


class _StaticSnowflakeExecutor:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def execute(self, _config, sql: str) -> dict:
        return {**self.payload, "sql": sql}


def test_create_conversation_persists_selected_agent_ids(tmp_path):
    db_path = tmp_path / "chatroom.sqlite3"
    with _connect_for_assertion(db_path) as connection:
        custom = create_custom_agent(
            connection,
            name="Account Helper",
            description="Looks up business accounts.",
            system_prompt="Use the external account API.",
            tools=["lookup_account"]
        )

    def override_connection() -> Iterator[sqlite3.Connection]:
        connection = connect_database(db_path)
        try:
            yield connection
        finally:
            connection.close()

    app.dependency_overrides[get_database_connection] = override_connection
    try:
        response = TestClient(app).post(
            "/conversations",
            json={"selected_agent_ids": ["supervisor", custom.id]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    payload = response.json()

    assert payload["title"] == "New conversation"
    assert payload["selected_agent_ids"] == [
        "supervisor",
        "connector_sales_pipeline",
        "connector_account_directory",
        custom.id,
    ]
    assert payload["created_at"]

    with _connect_for_assertion(db_path) as connection:
        stored = get_conversation(connection, payload["id"])
        assert stored is not None
        assert stored.selected_agent_ids == [
            "supervisor",
            "connector_sales_pipeline",
            "connector_account_directory",
            custom.id,
        ]


def test_create_conversation_implicit_supervisor_when_no_agents_selected(tmp_path):
    def override_connection() -> Iterator[sqlite3.Connection]:
        connection = connect_database(tmp_path / "chatroom.sqlite3")
        try:
            yield connection
        finally:
            connection.close()

    app.dependency_overrides[get_database_connection] = override_connection
    try:
        response = TestClient(app).post(
            "/conversations",
            json={"selected_agent_ids": []},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201
    assert response.json()["selected_agent_ids"] == [
        "supervisor",
        "connector_sales_pipeline",
        "connector_account_directory",
    ]


def test_create_conversation_adds_implicit_supervisor_for_custom_agents(tmp_path):
    db_path = tmp_path / "chatroom.sqlite3"
    with _connect_for_assertion(db_path) as connection:
        custom = create_custom_agent(
            connection,
            name="Snowflake Analyst",
            description="Runs Snowflake queries.",
            system_prompt="Query Snowflake for revenue answers.",
            tools=["query_snowflake"]
        )

    def override_connection() -> Iterator[sqlite3.Connection]:
        connection = connect_database(db_path)
        try:
            yield connection
        finally:
            connection.close()

    app.dependency_overrides[get_database_connection] = override_connection
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


def test_create_conversation_rejects_unknown_agent_id(tmp_path):
    def override_connection() -> Iterator[sqlite3.Connection]:
        connection = connect_database(tmp_path / "chatroom.sqlite3")
        try:
            yield connection
        finally:
            connection.close()

    app.dependency_overrides[get_database_connection] = override_connection
    try:
        response = TestClient(app).post(
            "/conversations",
            json={"selected_agent_ids": ["supervisor", "missing"]},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "bad_request",
            "message": "Unknown selected_agent_ids: missing",
        }
    }


def test_list_conversations_returns_saved_conversations(tmp_path):
    db_path = tmp_path / "chatroom.sqlite3"
    with _connect_for_assertion(db_path) as connection:
        first = create_conversation(
            connection,
            selected_agent_ids=["supervisor"],
        )
        second = create_conversation(
            connection,
            selected_agent_ids=["supervisor"],
        )

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        response = TestClient(app).get("/conversations")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    conversations_by_id = {
        conversation["id"]: conversation for conversation in response.json()
    }
    assert conversations_by_id == {
        first.id: {
            "id": first.id,
            "title": "New conversation",
            "selected_agent_ids": ["supervisor"],
            "created_at": first.created_at,
        },
        second.id: {
            "id": second.id,
            "title": "New conversation",
            "selected_agent_ids": ["supervisor"],
            "created_at": second.created_at,
        },
    }


def test_get_conversation_returns_metadata_and_ordered_messages(tmp_path):
    db_path = tmp_path / "chatroom.sqlite3"
    with _connect_for_assertion(db_path) as connection:
        created = create_conversation(
            connection,
            selected_agent_ids=["supervisor", "summarizer"],
        )
        first = append_message(
            connection,
            conversation_id=created.id,
            role="user",
            content="Summarize revenue by region.",
        )
        second = append_message(
            connection,
            conversation_id=created.id,
            role="assistant",
            content="Revenue was strongest in the South.",
            agent_name="supervisor",
        )
        artifact = append_artifact(
            connection,
            conversation_id=created.id,
            message_id=second.id,
            artifact_type="chart",
            title="Revenue by Region",
            payload={
                "agent_id": "visualizer",
                "spec": {
                    "chart_type": "bar",
                    "title": "Revenue by Region",
                    "series": [{"label": "South", "value": 34875.0}],
                },
            },
        )
        event = append_group_chat_event(
            connection,
            conversation_id=created.id,
            event_type="final_answer",
            agent_id=None,
            content="Revenue was strongest in the South.",
            payload={"artifact_count": 0},
        )

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        response = TestClient(app).get(f"/conversations/{created.id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()

    assert payload["id"] == created.id
    assert payload["title"] == "New conversation"
    assert payload["selected_agent_ids"] == ["supervisor", "summarizer"]
    assert payload["created_at"] == created.created_at
    assert payload["messages"] == [
        {
            "id": first.id,
            "conversation_id": created.id,
            "role": "user",
            "content": "Summarize revenue by region.",
            "agent_name": None,
            "provider_id": None,
            "model_name": None,
            "created_at": first.created_at,
        },
        {
            "id": second.id,
            "conversation_id": created.id,
            "role": "assistant",
            "content": "Revenue was strongest in the South.",
            "agent_name": "supervisor",
            "provider_id": None,
            "model_name": None,
            "created_at": second.created_at,
        },
    ]
    assert payload["group_chat_events"] == [
        {
            "id": event.id,
            "conversation_id": created.id,
            "event_type": "final_answer",
            "agent_id": None,
            "content": "Revenue was strongest in the South.",
            "payload": {"artifact_count": 0},
            "created_at": event.created_at,
        }
    ]
    assert payload["artifacts"] == [
        {
            "id": artifact.id,
            "conversation_id": created.id,
            "message_id": second.id,
            "artifact_type": "chart",
            "title": "Revenue by Region",
            "payload": {
                "agent_id": "visualizer",
                "spec": {
                    "chart_type": "bar",
                    "title": "Revenue by Region",
                    "series": [{"label": "South", "value": 34875.0}],
                },
            },
            "created_at": artifact.created_at,
        }
    ]


def test_get_conversation_returns_404_for_missing_conversation(tmp_path):
    db_path = tmp_path / "chatroom.sqlite3"

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        response = TestClient(app).get("/conversations/missing")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "not_found",
            "message": "Conversation not found: missing",
        }
    }


def test_stream_message_streams_supervisor_text_and_persists_exchange(tmp_path, monkeypatch):
    db_path = tmp_path / "chatroom.sqlite3"
    settings = _external_api_settings()
    with _connect_for_assertion(db_path) as connection:
        custom = create_custom_agent(
            connection,
            name="Account Helper",
            description="Looks up business accounts.",
            system_prompt="Use the external account API.",
            tools=["lookup_account"]
        )
        created = create_conversation(
            connection,
            selected_agent_ids=[custom.id],
        )

    class FakeProvider:
        model = "fake-supervisor-model"

        def generate(self, messages, *, tools=()):
            if tools:
                return ModelResponse(
                    content="",
                    tool_calls=(
                        ToolCall(
                            name="lookup_account",
                            arguments={"account_id": "AC-1001"},
                        ),
                    ),
                )
            return ModelResponse(content=f'{{"agent_ids": ["{custom.id}"]}}')

        def stream(self, messages, *, tools=()):
            raise AssertionError("ProviderSupervisor should not stream provider text.")

    monkeypatch.setattr(
        "app.services.chat_turn.create_model_provider",
        lambda _settings: FakeProvider(),
    )

    set_http_transport(FakeHttpTransport())
    with patch("app.tool_registry.get_settings", return_value=settings), patch(
        "app.connectors.external_api.get_settings", return_value=settings
    ):
        app.dependency_overrides[get_database_connection] = _override_connection(db_path)
        try:
            response = TestClient(app).post(
                f"/conversations/{created.id}/messages/stream",
                json={"content": "Look up account AC-1001"},
            )
        finally:
            app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "Account AC-1001 is Northwind Traders" in response.text

    with _connect_for_assertion(db_path) as connection:
        messages = list_messages(connection, created.id)
        traces = list_tool_traces(connection, created.id)
        events = list_group_chat_events(connection, created.id)
        stored = get_conversation(connection, created.id)

    assert stored is not None
    assert stored.title == "Look up account AC-1001"
    assert len(messages) == 2
    assert messages[0].role == "user"
    assert messages[0].content == "Look up account AC-1001"
    assert messages[0].agent_name is None
    assert messages[1].role == "assistant"
    assert messages[1].content == response.text
    assert messages[1].agent_name == "supervisor"
    assert traces == []
    assert [event.event_type for event in events] == [
        "manager_started",
        "specialist_selected",
        "tool_called",
        "tool_finished",
        "specialist_answered",
        "final_answer",
    ]
    assert events[1].agent_id == custom.id
    assert events[2].payload["tool_name"] == "lookup_account"
    assert events[-1].content == response.text


def test_stream_message_persists_snowflake_chart_artifacts(tmp_path, monkeypatch):
    db_path = tmp_path / "chatroom.sqlite3"
    captured_messages: list[ModelMessage] = []
    settings = _local_snowflake_settings()

    with _connect_for_assertion(db_path) as connection:
        custom = create_custom_agent(
            connection,
            name="Snowflake Analyst",
            description="Runs Snowflake queries.",
            system_prompt="Use Snowflake.",
            tools=["query_snowflake"]
        )

    snowflake_payload = {
        "columns": ["region", "total_revenue"],
        "row_count": 2,
        "rows": [
            {"region": "West", "total_revenue": 100.0},
            {"region": "East", "total_revenue": 200.0},
        ],
    }
    set_snowflake_executor(_StaticSnowflakeExecutor(snowflake_payload))

    class FakeProvider:
        model = "fake-supervisor-model"

        def generate(self, messages, *, tools=()):
            captured_messages.extend(messages)
            if tools:
                return ModelResponse(
                    content="",
                    tool_calls=(
                        ToolCall(
                            name="query_snowflake",
                            arguments={
                                "sql": (
                                    "SELECT region, SUM(CAST(revenue AS REAL)) "
                                    "AS total_revenue FROM pipeline_deals "
                                    "WHERE stage = 'Closed Won' "
                                    "GROUP BY region LIMIT 10"
                                ),
                                "max_rows": 10,
                            },
                        ),
                    ),
                )
            return ModelResponse(content=f'{{"agent_ids": ["{custom.id}"]}}')

        def stream(self, messages, *, tools=()):
            raise AssertionError("ProviderSupervisor should not stream provider text.")

    def fake_create_model_provider(_settings):
        return FakeProvider()

    monkeypatch.setattr(
        "app.services.chat_turn.create_model_provider",
        fake_create_model_provider,
    )
    monkeypatch.setattr("app.tool_registry.get_settings", lambda: settings)
    monkeypatch.setattr("app.connectors.snowflake.get_settings", lambda: settings)

    with _connect_for_assertion(db_path) as connection:
        created = create_conversation(
            connection,
            selected_agent_ids=[custom.id],
        )

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        response = TestClient(app).post(
            f"/conversations/{created.id}/messages/stream",
            json={
                "content": "Summarize revenue by region as bullets and make a chart.",
            },
        )
    finally:
        app.dependency_overrides.clear()
        set_snowflake_executor(None)

    assert response.status_code == 200
    assert "Returned 2 rows:" in response.text
    assert "Matched 2 rows." in response.text
    assert captured_messages[0].role == "system"
    assert "local group chat manager" in captured_messages[0].content
    assert custom.id in captured_messages[1].content

    with _connect_for_assertion(db_path) as connection:
        messages = list_messages(connection, created.id)
        events = list_group_chat_events(connection, created.id)
        artifacts = list_artifacts(connection, created.id)
        stored = get_conversation(connection, created.id)

    assert stored is not None
    assert stored.title == "Summarize revenue by region as bullets and make a chart."
    assert messages[1].role == "assistant"
    assert messages[1].agent_name == "supervisor"
    assert messages[1].provider_id == "ollama"
    assert messages[1].model_name == "fake-supervisor-model"
    assert len(artifacts) == 1
    assert artifacts[0].message_id == messages[1].id
    assert artifacts[0].artifact_type == "chart"
    assert artifacts[0].title == "Revenue by Region (bar)"
    assert artifacts[0].payload["agent_id"] == "visualizer"
    assert artifacts[0].payload["spec"]["chart_type"] == "bar"
    assert artifacts[0].payload["spec"]["title"] == "Revenue by Region (bar)"
    assert [event.event_type for event in events] == [
        "manager_started",
        "specialist_selected",
        "tool_called",
        "tool_finished",
        "specialist_answered",
        "specialist_selected",
        "tool_called",
        "tool_finished",
        "specialist_answered",
        "specialist_selected",
        "tool_called",
        "tool_finished",
        "specialist_answered",
        "final_answer",
    ]


def test_stream_message_returns_404_for_missing_conversation(tmp_path):
    db_path = tmp_path / "chatroom.sqlite3"

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        response = TestClient(app).post(
            "/conversations/missing/messages/stream",
            json={"content": "Hello?"},
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


def test_title_from_first_message_truncates_long_questions():
    from app.services.chat_turn import title_from_first_message as _title_from_first_message

    long_question = (
        "Can you please summarize the revenue by region for the last fiscal year "
        "and then prepare a chart comparing West versus East performance?"
    )
    title = _title_from_first_message(long_question)

    assert title.endswith("…")
    assert len(title) <= 72
    assert "summarize the revenue" in title.lower()


def test_stream_message_keeps_custom_title_and_does_not_retitle_later(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "chatroom.sqlite3"

    with _connect_for_assertion(db_path) as connection:
        created = create_conversation(
            connection,
            selected_agent_ids=["supervisor"],
            title="Custom title",
        )

    class FakeProvider:
        model = "fake-supervisor-model"
        calls = 0

        def generate(self, messages, *, tools=()):
            FakeProvider.calls += 1
            return ModelResponse(content=f"Answer {FakeProvider.calls}")

        def stream(self, messages, *, tools=()):
            raise AssertionError("ProviderSupervisor should not stream provider text.")

    monkeypatch.setattr(
        "app.services.chat_turn.create_model_provider",
        lambda _settings: FakeProvider(),
    )

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        first = TestClient(app).post(
            f"/conversations/{created.id}/messages/stream",
            json={"content": "First question about pipeline"},
        )
        second = TestClient(app).post(
            f"/conversations/{created.id}/messages/stream",
            json={"content": "Second follow-up question"},
        )
    finally:
        app.dependency_overrides.clear()

    assert first.status_code == 200
    assert second.status_code == 200

    with _connect_for_assertion(db_path) as connection:
        stored = get_conversation(connection, created.id)

    assert stored is not None
    assert stored.title == "Custom title"


def test_stream_message_provider_failure_does_not_persist_partial_turn(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "chatroom.sqlite3"

    with _connect_for_assertion(db_path) as connection:
        created = create_conversation(
            connection,
            selected_agent_ids=["supervisor"],
        )

    class FailingProvider:
        model = "fake-supervisor-model"

        def generate(self, messages, *, tools=()):
            raise RuntimeError("provider unavailable")

        def stream(self, messages, *, tools=()):
            raise AssertionError("stream should not be used")

    monkeypatch.setattr(
        "app.services.chat_turn.create_model_provider",
        lambda _settings: FailingProvider(),
    )

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        response = TestClient(app).post(
            f"/conversations/{created.id}/messages/stream",
            json={"content": "Will this leave an orphan user message?"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "provider unavailable" in response.json()["error"]["message"]

    with _connect_for_assertion(db_path) as connection:
        messages = list_messages(connection, created.id)
        events = list_group_chat_events(connection, created.id)
        stored = get_conversation(connection, created.id)

    assert stored is not None
    assert stored.title == "New conversation"
    assert messages == []
    assert events == []


def test_stream_message_persists_completed_turn_atomically(tmp_path, monkeypatch):
    db_path = tmp_path / "chatroom.sqlite3"

    with _connect_for_assertion(db_path) as connection:
        custom = create_custom_agent(
            connection,
            name="Helper",
            description="Answers simple questions.",
            system_prompt="Be brief.",
            tools=[],
        )
        created = create_conversation(
            connection,
            selected_agent_ids=["supervisor", custom.id],
        )

    class FakeProvider:
        model = "fake-supervisor-model"
        calls = 0

        def generate(self, messages, *, tools=()):
            FakeProvider.calls += 1
            if FakeProvider.calls == 1:
                return ModelResponse(content=f'{{"agent_ids": ["{custom.id}"]}}')
            return ModelResponse(content="Completed answer")

        def stream(self, messages, *, tools=()):
            raise AssertionError("stream should not be used")

    monkeypatch.setattr(
        "app.services.chat_turn.create_model_provider",
        lambda _settings: FakeProvider(),
    )

    app.dependency_overrides[get_database_connection] = _override_connection(db_path)
    try:
        response = TestClient(app).post(
            f"/conversations/{created.id}/messages/stream",
            json={"content": "Persist this turn together"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.headers.get("X-Stream-Mode") == "buffered"
    assert response.text == "Completed answer"

    with _connect_for_assertion(db_path) as connection:
        messages = list_messages(connection, created.id)
        events = list_group_chat_events(connection, created.id)
        stored = get_conversation(connection, created.id)

    assert stored is not None
    assert stored.title == "Persist this turn together"
    assert [message.role for message in messages] == ["user", "assistant"]
    assert messages[1].content == "Completed answer"
    assert "manager_started" in [event.event_type for event in events]
    assert events[-1].event_type == "final_answer"
    assert events[-1].content == "Completed answer"

def _override_connection(db_path: Path):
    def override_connection() -> Iterator[sqlite3.Connection]:
        connection = connect_database(db_path)
        try:
            yield connection
        finally:
            connection.close()

    return override_connection


@contextmanager
def _connect_for_assertion(db_path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect_database(db_path)
    try:
        yield connection
    finally:
        connection.close()
