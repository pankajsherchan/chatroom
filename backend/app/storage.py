"""Local SQLite persistence for conversations, messages, and inspect events."""

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence
from uuid import uuid4


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    selected_agent_ids TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant', 'system', 'tool')),
    content TEXT NOT NULL,
    agent_name TEXT,
    provider_id TEXT,
    model_name TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id)
        REFERENCES conversations (id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_created_at
    ON messages (conversation_id, created_at);

CREATE TABLE IF NOT EXISTS tool_traces (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    tool_name TEXT NOT NULL,
    arguments TEXT NOT NULL,
    output TEXT,
    error TEXT,
    status TEXT NOT NULL CHECK (status IN ('success', 'error')),
    provider_id TEXT,
    duration_ms INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id)
        REFERENCES conversations (id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tool_traces_conversation_created_at
    ON tool_traces (conversation_id, created_at);

CREATE TABLE IF NOT EXISTS group_chat_events (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    event_type TEXT NOT NULL CHECK (
        event_type IN (
            'manager_started',
            'specialist_selected',
            'tool_called',
            'tool_finished',
            'specialist_answered',
            'final_answer'
        )
    ),
    agent_id TEXT,
    content TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id)
        REFERENCES conversations (id)
        ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_group_chat_events_conversation_created_at
    ON group_chat_events (conversation_id, created_at);

CREATE TABLE IF NOT EXISTS artifacts (
    id TEXT PRIMARY KEY,
    conversation_id TEXT NOT NULL,
    message_id TEXT,
    artifact_type TEXT NOT NULL CHECK (artifact_type IN ('chart')),
    title TEXT NOT NULL,
    payload TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id)
        REFERENCES conversations (id)
        ON DELETE CASCADE,
    FOREIGN KEY (message_id)
        REFERENCES messages (id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_artifacts_conversation_created_at
    ON artifacts (conversation_id, created_at);

CREATE TABLE IF NOT EXISTS custom_agents (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    system_prompt TEXT NOT NULL,
    tools TEXT NOT NULL,
    model_provider TEXT NOT NULL DEFAULT 'ollama',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_custom_agents_updated_at
    ON custom_agents (updated_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS imported_datasets (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    file_path TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    columns_json TEXT NOT NULL,
    tool_name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_imported_datasets_updated_at
    ON imported_datasets (updated_at DESC, id DESC);
"""

CONVERSATION_COLUMNS = (
    "id",
    "title",
    "selected_agent_ids",
    "created_at",
)

MESSAGE_COLUMNS = (
    "id",
    "conversation_id",
    "role",
    "content",
    "agent_name",
    "provider_id",
    "model_name",
    "created_at",
)

TOOL_TRACE_COLUMNS = (
    "id",
    "conversation_id",
    "tool_name",
    "arguments",
    "output",
    "error",
    "status",
    "provider_id",
    "duration_ms",
    "created_at",
)

GROUP_CHAT_EVENT_COLUMNS = (
    "id",
    "conversation_id",
    "event_type",
    "agent_id",
    "content",
    "payload",
    "created_at",
)

ARTIFACT_COLUMNS = (
    "id",
    "conversation_id",
    "message_id",
    "artifact_type",
    "title",
    "payload",
    "created_at",
)

CUSTOM_AGENT_COLUMNS = (
    "id",
    "name",
    "description",
    "system_prompt",
    "tools",
    "created_at",
    "updated_at",
)


@dataclass(frozen=True)
class Conversation:
    id: str
    title: str
    selected_agent_ids: list[str]
    created_at: str


@dataclass(frozen=True)
class Message:
    id: str
    conversation_id: str
    role: str
    content: str
    agent_name: str | None
    provider_id: str | None
    model_name: str | None
    created_at: str


@dataclass(frozen=True)
class ToolTrace:
    id: str
    conversation_id: str
    tool_name: str
    arguments: dict[str, Any]
    output: dict[str, Any] | None
    error: str | None
    status: str
    provider_id: str | None
    duration_ms: int
    created_at: str


@dataclass(frozen=True)
class GroupChatEventRecord:
    id: str
    conversation_id: str
    event_type: str
    agent_id: str | None
    content: str
    payload: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class Artifact:
    id: str
    conversation_id: str
    message_id: str | None
    artifact_type: str
    title: str
    payload: dict[str, Any]
    created_at: str


@dataclass(frozen=True)
class CustomAgentRecord:
    id: str
    name: str
    description: str
    system_prompt: str
    tools: list[str]
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class ImportedDatasetRecord:
    id: str
    name: str
    description: str
    file_path: Path
    original_filename: str
    columns: list["DatasetColumnRecord"]
    tool_name: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class DatasetColumnRecord:
    name: str
    column_type: str


def connect_database(db_path: Path) -> sqlite3.Connection:
    """Open a SQLite database and ensure the local schema exists."""

    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.executescript(SCHEMA_SQL)
    return connection


def create_conversation(
    connection: sqlite3.Connection,
    *,
    selected_agent_ids: Sequence[str],
    title: str = "New conversation",
) -> Conversation:
    conversation_id = str(uuid4())
    selected_agent_ids_json = json.dumps(list(selected_agent_ids))
    row = connection.execute(
        """
        INSERT INTO conversations (id, title, selected_agent_ids)
        VALUES (?, ?, ?)
        RETURNING id, title, selected_agent_ids, created_at
        """,
        (conversation_id, title, selected_agent_ids_json),
    ).fetchone()
    connection.commit()
    return _conversation_from_row(row)


def get_conversation(
    connection: sqlite3.Connection,
    conversation_id: str,
) -> Conversation | None:
    row = connection.execute(
        """
        SELECT id, title, selected_agent_ids, created_at
        FROM conversations
        WHERE id = ?
        """,
        (conversation_id,),
    ).fetchone()
    if row is None:
        return None
    return _conversation_from_row(row)


def list_conversations(connection: sqlite3.Connection) -> list[Conversation]:
    rows = connection.execute(
        """
        SELECT id, title, selected_agent_ids, created_at
        FROM conversations
        ORDER BY created_at DESC, id DESC
        """
    ).fetchall()
    return [_conversation_from_row(row) for row in rows]


def update_conversation_title(
    connection: sqlite3.Connection,
    conversation_id: str,
    *,
    title: str,
) -> Conversation | None:
    row = connection.execute(
        """
        UPDATE conversations
        SET title = ?
        WHERE id = ?
        RETURNING id, title, selected_agent_ids, created_at
        """,
        (title, conversation_id),
    ).fetchone()
    if row is None:
        return None
    connection.commit()
    return _conversation_from_row(row)


def delete_conversation(
    connection: sqlite3.Connection,
    conversation_id: str,
) -> bool:
    cursor = connection.execute(
        """
        DELETE FROM conversations
        WHERE id = ?
        """,
        (conversation_id,),
    )
    connection.commit()
    return cursor.rowcount > 0


def append_message(
    connection: sqlite3.Connection,
    *,
    conversation_id: str,
    role: str,
    content: str,
    agent_name: str | None = None,
    provider_id: str | None = None,
    model_name: str | None = None,
) -> Message:
    message_id = str(uuid4())
    row = connection.execute(
        """
        INSERT INTO messages (id, conversation_id, role, content, agent_name, provider_id, model_name)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING id, conversation_id, role, content, agent_name, provider_id, model_name, created_at
        """,
        (message_id, conversation_id, role, content, agent_name, provider_id, model_name),
    ).fetchone()
    connection.commit()
    return _message_from_row(row)


def list_messages(
    connection: sqlite3.Connection,
    conversation_id: str,
) -> list[Message]:
    rows = connection.execute(
        """
        SELECT id, conversation_id, role, content, agent_name, provider_id, model_name, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY created_at ASC, rowid ASC
        """,
        (conversation_id,),
    ).fetchall()
    return [_message_from_row(row) for row in rows]


def append_tool_trace(
    connection: sqlite3.Connection,
    *,
    conversation_id: str,
    tool_name: str,
    arguments: dict[str, Any],
    output: dict[str, Any] | None,
    error: str | None,
    status: str,
    provider_id: str | None,
    duration_ms: int,
) -> ToolTrace:
    trace_id = str(uuid4())
    row = connection.execute(
        """
        INSERT INTO tool_traces (
            id,
            conversation_id,
            tool_name,
            arguments,
            output,
            error,
            status,
            provider_id,
            duration_ms
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        RETURNING id,
            conversation_id,
            tool_name,
            arguments,
            output,
            error,
            status,
            provider_id,
            duration_ms,
            created_at
        """,
        (
            trace_id,
            conversation_id,
            tool_name,
            json.dumps(arguments, sort_keys=True),
            json.dumps(output, sort_keys=True) if output is not None else None,
            error,
            status,
            provider_id,
            duration_ms,
        ),
    ).fetchone()
    connection.commit()
    return _tool_trace_from_row(row)


def list_tool_traces(
    connection: sqlite3.Connection,
    conversation_id: str,
) -> list[ToolTrace]:
    rows = connection.execute(
        """
        SELECT id,
            conversation_id,
            tool_name,
            arguments,
            output,
            error,
            status,
            provider_id,
            duration_ms,
            created_at
        FROM tool_traces
        WHERE conversation_id = ?
        ORDER BY created_at ASC, rowid ASC
        """,
        (conversation_id,),
    ).fetchall()
    return [_tool_trace_from_row(row) for row in rows]


def append_group_chat_event(
    connection: sqlite3.Connection,
    *,
    conversation_id: str,
    event_type: str,
    agent_id: str | None,
    content: str,
    payload: dict[str, Any],
) -> GroupChatEventRecord:
    event_id = str(uuid4())
    row = connection.execute(
        """
        INSERT INTO group_chat_events (
            id,
            conversation_id,
            event_type,
            agent_id,
            content,
            payload
        )
        VALUES (?, ?, ?, ?, ?, ?)
        RETURNING id,
            conversation_id,
            event_type,
            agent_id,
            content,
            payload,
            created_at
        """,
        (
            event_id,
            conversation_id,
            event_type,
            agent_id,
            content,
            json.dumps(payload, sort_keys=True),
        ),
    ).fetchone()
    connection.commit()
    return _group_chat_event_from_row(row)


def list_group_chat_events(
    connection: sqlite3.Connection,
    conversation_id: str,
) -> list[GroupChatEventRecord]:
    rows = connection.execute(
        """
        SELECT id,
            conversation_id,
            event_type,
            agent_id,
            content,
            payload,
            created_at
        FROM group_chat_events
        WHERE conversation_id = ?
        ORDER BY created_at ASC, rowid ASC
        """,
        (conversation_id,),
    ).fetchall()
    return [_group_chat_event_from_row(row) for row in rows]


def append_artifact(
    connection: sqlite3.Connection,
    *,
    conversation_id: str,
    artifact_type: str,
    title: str,
    payload: dict[str, Any],
    message_id: str | None = None,
) -> Artifact:
    artifact_id = str(uuid4())
    row = connection.execute(
        """
        INSERT INTO artifacts (
            id,
            conversation_id,
            message_id,
            artifact_type,
            title,
            payload
        )
        VALUES (?, ?, ?, ?, ?, ?)
        RETURNING id,
            conversation_id,
            message_id,
            artifact_type,
            title,
            payload,
            created_at
        """,
        (
            artifact_id,
            conversation_id,
            message_id,
            artifact_type,
            title,
            json.dumps(payload, sort_keys=True),
        ),
    ).fetchone()
    connection.commit()
    return _artifact_from_row(row)


def list_artifacts(
    connection: sqlite3.Connection,
    conversation_id: str,
) -> list[Artifact]:
    rows = connection.execute(
        """
        SELECT id,
            conversation_id,
            message_id,
            artifact_type,
            title,
            payload,
            created_at
        FROM artifacts
        WHERE conversation_id = ?
        ORDER BY created_at ASC, rowid ASC
        """,
        (conversation_id,),
    ).fetchall()
    return [_artifact_from_row(row) for row in rows]


def create_custom_agent(
    connection: sqlite3.Connection,
    *,
    name: str,
    description: str,
    system_prompt: str,
    tools: Sequence[str],
) -> CustomAgentRecord:
    agent_id = f"custom_{uuid4()}"
    tools_json = json.dumps(list(tools))
    row = connection.execute(
        """
        INSERT INTO custom_agents (
            id,
            name,
            description,
            system_prompt,
            tools
        )
        VALUES (?, ?, ?, ?, ?)
        RETURNING id,
            name,
            description,
            system_prompt,
            tools,
            created_at,
            updated_at
        """,
        (agent_id, name, description, system_prompt, tools_json),
    ).fetchone()
    connection.commit()
    return _custom_agent_from_row(row)


def get_custom_agent(
    connection: sqlite3.Connection,
    agent_id: str,
) -> CustomAgentRecord | None:
    row = connection.execute(
        """
        SELECT id,
            name,
            description,
            system_prompt,
            tools,
            created_at,
            updated_at
        FROM custom_agents
        WHERE id = ?
        """,
        (agent_id,),
    ).fetchone()
    if row is None:
        return None
    return _custom_agent_from_row(row)


def list_custom_agents(connection: sqlite3.Connection) -> list[CustomAgentRecord]:
    rows = connection.execute(
        """
        SELECT id,
            name,
            description,
            system_prompt,
            tools,
            created_at,
            updated_at
        FROM custom_agents
        ORDER BY updated_at DESC, id DESC
        """
    ).fetchall()
    return [_custom_agent_from_row(row) for row in rows]


def update_custom_agent(
    connection: sqlite3.Connection,
    agent_id: str,
    *,
    name: str,
    description: str,
    system_prompt: str,
    tools: Sequence[str],
) -> CustomAgentRecord | None:
    tools_json = json.dumps(list(tools))
    row = connection.execute(
        """
        UPDATE custom_agents
        SET name = ?,
            description = ?,
            system_prompt = ?,
            tools = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        RETURNING id,
            name,
            description,
            system_prompt,
            tools,
            created_at,
            updated_at
        """,
        (name, description, system_prompt, tools_json, agent_id),
    ).fetchone()
    if row is None:
        return None
    connection.commit()
    return _custom_agent_from_row(row)


def delete_custom_agent(connection: sqlite3.Connection, agent_id: str) -> bool:
    cursor = connection.execute(
        """
        DELETE FROM custom_agents
        WHERE id = ?
        """,
        (agent_id,),
    )
    connection.commit()
    return cursor.rowcount > 0


def create_imported_dataset(
    connection: sqlite3.Connection,
    *,
    name: str,
    description: str,
    source_csv_path: Path,
    original_filename: str,
    datasets_dir: Path,
    columns: Sequence[DatasetColumnRecord],
) -> ImportedDatasetRecord:
    dataset_id = f"dataset_{uuid4()}"
    tool_name = f"query_{dataset_id.replace('-', '_')}"
    datasets_dir.mkdir(parents=True, exist_ok=True)
    stored_path = datasets_dir / f"{dataset_id}.csv"
    stored_path.write_bytes(source_csv_path.read_bytes())

    columns_json = json.dumps(
        [{"name": column.name, "column_type": column.column_type} for column in columns]
    )
    row = connection.execute(
        """
        INSERT INTO imported_datasets (
            id,
            name,
            description,
            file_path,
            original_filename,
            columns_json,
            tool_name
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        RETURNING id,
            name,
            description,
            file_path,
            original_filename,
            columns_json,
            tool_name,
            created_at,
            updated_at
        """,
        (
            dataset_id,
            name,
            description,
            str(stored_path),
            original_filename,
            columns_json,
            tool_name,
        ),
    ).fetchone()
    connection.commit()
    return _imported_dataset_from_row(row)


def get_imported_dataset(
    connection: sqlite3.Connection,
    dataset_id: str,
) -> ImportedDatasetRecord | None:
    row = connection.execute(
        """
        SELECT id,
            name,
            description,
            file_path,
            original_filename,
            columns_json,
            tool_name,
            created_at,
            updated_at
        FROM imported_datasets
        WHERE id = ?
        """,
        (dataset_id,),
    ).fetchone()
    if row is None:
        return None
    return _imported_dataset_from_row(row)


def get_imported_dataset_by_tool_name(
    connection: sqlite3.Connection,
    tool_name: str,
) -> ImportedDatasetRecord | None:
    row = connection.execute(
        """
        SELECT id,
            name,
            description,
            file_path,
            original_filename,
            columns_json,
            tool_name,
            created_at,
            updated_at
        FROM imported_datasets
        WHERE tool_name = ?
        """,
        (tool_name,),
    ).fetchone()
    if row is None:
        return None
    return _imported_dataset_from_row(row)


def list_imported_datasets(connection: sqlite3.Connection) -> list[ImportedDatasetRecord]:
    rows = connection.execute(
        """
        SELECT id,
            name,
            description,
            file_path,
            original_filename,
            columns_json,
            tool_name,
            created_at,
            updated_at
        FROM imported_datasets
        ORDER BY updated_at DESC, id DESC
        """
    ).fetchall()
    return [_imported_dataset_from_row(row) for row in rows]


def delete_imported_dataset(connection: sqlite3.Connection, dataset_id: str) -> bool:
    record = get_imported_dataset(connection, dataset_id)
    if record is None:
        return False

    cursor = connection.execute(
        """
        DELETE FROM imported_datasets
        WHERE id = ?
        """,
        (dataset_id,),
    )
    connection.commit()
    if record.file_path.exists():
        record.file_path.unlink()
    return cursor.rowcount > 0


def _conversation_from_row(row: sqlite3.Row) -> Conversation:
    return Conversation(
        id=row["id"],
        title=row["title"],
        selected_agent_ids=json.loads(row["selected_agent_ids"]),
        created_at=row["created_at"],
    )


def _message_from_row(row: sqlite3.Row) -> Message:
    return Message(
        id=row["id"],
        conversation_id=row["conversation_id"],
        role=row["role"],
        content=row["content"],
        agent_name=row["agent_name"],
        provider_id=row["provider_id"],
        model_name=row["model_name"],
        created_at=row["created_at"],
    )


def _tool_trace_from_row(row: sqlite3.Row) -> ToolTrace:
    return ToolTrace(
        id=row["id"],
        conversation_id=row["conversation_id"],
        tool_name=row["tool_name"],
        arguments=json.loads(row["arguments"]),
        output=json.loads(row["output"]) if row["output"] is not None else None,
        error=row["error"],
        status=row["status"],
        provider_id=row["provider_id"],
        duration_ms=row["duration_ms"],
        created_at=row["created_at"],
    )


def _group_chat_event_from_row(row: sqlite3.Row) -> GroupChatEventRecord:
    return GroupChatEventRecord(
        id=row["id"],
        conversation_id=row["conversation_id"],
        event_type=row["event_type"],
        agent_id=row["agent_id"],
        content=row["content"],
        payload=json.loads(row["payload"]),
        created_at=row["created_at"],
    )


def _artifact_from_row(row: sqlite3.Row) -> Artifact:
    return Artifact(
        id=row["id"],
        conversation_id=row["conversation_id"],
        message_id=row["message_id"],
        artifact_type=row["artifact_type"],
        title=row["title"],
        payload=json.loads(row["payload"]),
        created_at=row["created_at"],
    )


def _custom_agent_from_row(row: sqlite3.Row) -> CustomAgentRecord:
    return CustomAgentRecord(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        system_prompt=row["system_prompt"],
        tools=json.loads(row["tools"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _imported_dataset_from_row(row: sqlite3.Row) -> ImportedDatasetRecord:
    return ImportedDatasetRecord(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        file_path=Path(row["file_path"]),
        original_filename=row["original_filename"],
        columns=[
            DatasetColumnRecord(name=item["name"], column_type=item["column_type"])
            for item in json.loads(row["columns_json"])
        ],
        tool_name=row["tool_name"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
