import sqlite3

from app.storage import (
    ARTIFACT_COLUMNS,
    CONVERSATION_COLUMNS,
    GROUP_CHAT_EVENT_COLUMNS,
    MESSAGE_COLUMNS,
    SCHEMA_SQL,
    TOOL_TRACE_COLUMNS,
    connect_database,
)


def test_schema_creates_conversations_and_messages_tables():
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA_SQL)

    conversation_columns = _table_columns(connection, "conversations")
    message_columns = _table_columns(connection, "messages")
    tool_trace_columns = _table_columns(connection, "tool_traces")
    group_chat_event_columns = _table_columns(connection, "group_chat_events")
    artifact_columns = _table_columns(connection, "artifacts")

    assert conversation_columns == list(CONVERSATION_COLUMNS)
    assert message_columns == list(MESSAGE_COLUMNS)
    assert tool_trace_columns == list(TOOL_TRACE_COLUMNS)
    assert group_chat_event_columns == list(GROUP_CHAT_EVENT_COLUMNS)
    assert artifact_columns == list(ARTIFACT_COLUMNS)


def test_schema_cascades_deleted_conversations_to_messages():
    connection = sqlite3.connect(":memory:")
    connection.executescript(SCHEMA_SQL)

    connection.execute(
        """
        INSERT INTO conversations (id, title, selected_agent_ids)
        VALUES ('conversation-1', 'Demo', '["supervisor"]')
        """
    )
    connection.execute(
        """
        INSERT INTO messages (id, conversation_id, role, content)
        VALUES ('message-1', 'conversation-1', 'user', 'hello')
        """
    )
    connection.execute(
        """
        INSERT INTO tool_traces (
            id,
            conversation_id,
            tool_name,
            arguments,
            status,
            duration_ms
        )
        VALUES (
            'trace-1',
            'conversation-1',
            'query_snowflake',
            '{}',
            'success',
            1
        )
        """
    )
    connection.execute(
        """
        INSERT INTO group_chat_events (
            id,
            conversation_id,
            event_type,
            content,
            payload
        )
        VALUES (
            'event-1',
            'conversation-1',
            'manager_started',
            'Started.',
            '{}'
        )
        """
    )
    connection.execute(
        """
        INSERT INTO artifacts (
            id,
            conversation_id,
            artifact_type,
            title,
            payload
        )
        VALUES (
            'artifact-1',
            'conversation-1',
            'chart',
            'Revenue by Region',
            '{}'
        )
        """
    )

    connection.execute("DELETE FROM conversations WHERE id = 'conversation-1'")
    message_count = connection.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    trace_count = connection.execute("SELECT COUNT(*) FROM tool_traces").fetchone()[0]
    event_count = connection.execute(
        "SELECT COUNT(*) FROM group_chat_events"
    ).fetchone()[0]
    artifact_count = connection.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]

    assert message_count == 0
    assert trace_count == 0
    assert event_count == 0
    assert artifact_count == 0


def test_connect_database_creates_file_parent_and_schema(tmp_path):
    db_path = tmp_path / "nested" / "chatroom.sqlite3"

    connection = connect_database(db_path)

    assert db_path.exists()
    assert connection.row_factory is sqlite3.Row
    assert _foreign_keys_enabled(connection)
    assert _table_columns(connection, "conversations") == list(CONVERSATION_COLUMNS)
    assert _table_columns(connection, "messages") == list(MESSAGE_COLUMNS)
    assert _table_columns(connection, "tool_traces") == list(TOOL_TRACE_COLUMNS)
    assert _table_columns(connection, "group_chat_events") == list(
        GROUP_CHAT_EVENT_COLUMNS
    )
    assert _table_columns(connection, "artifacts") == list(ARTIFACT_COLUMNS)

    connection.close()


def _table_columns(connection: sqlite3.Connection, table_name: str) -> list[str]:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    return [row[1] for row in rows]


def _foreign_keys_enabled(connection: sqlite3.Connection) -> bool:
    return connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
