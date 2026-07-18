# Low-Level Design

Concise implementation reference for ChatRoom. The source of truth remains the code: `backend/app/storage.py` for schema and `backend/app/main.py` for application wiring.

## Repository Layout

```text
backend/app/             FastAPI API, orchestration, providers, and storage
backend/app/supervisor/  Manager, handoffs, specialists, and synthesis
backend/tools/           Local tool definitions
backend/tests/           Backend test suite
frontend/src/            React application
mock_services/           Local connector services and synthetic data
docs/                    Architecture references
```

## Storage

SQLite connections enable foreign keys and apply `SCHEMA_SQL` on startup.

| Table | Purpose | Key relationships |
| --- | --- | --- |
| `conversations` | Title and selected agent ids | Parent of turn data |
| `messages` | User and assistant history | Cascades with conversation |
| `group_chat_events` | Inspect trace | Cascades with conversation |
| `artifacts` | Chart specifications | Optional assistant message reference |
| `custom_agents` | Instructions and tool allowlist | Resolved at runtime |
| `imported_datasets` | CSV metadata and tool name | File stored on disk |
| `tool_traces` | Legacy trace compatibility | Not used by the active chat path |

Conversation writes normalize agent ids: `supervisor` comes first, configured connector agents follow, then custom specialists.

## HTTP API

Base URL: `http://127.0.0.1:8001`. Swagger UI is available at `/docs`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Backend and active-provider status |
| `GET` | `/providers/health` | Provider readiness and optional live check |
| `PUT` | `/providers/active` | Change the process-wide active provider |
| `GET` | `/agents` | Agent catalog and team metadata |
| `GET` | `/tools` | UI-assignable tool schemas |
| `GET` | `/connectors` | Connector readiness |
| `GET/POST` | `/custom-agents` | List and create custom agents |
| `GET/PUT/DELETE` | `/custom-agents/{id}` | Manage a custom agent |
| `GET/POST` | `/datasets` | List or upload CSV datasets |
| `GET/DELETE` | `/datasets/{id}` | Read or delete a dataset |
| `GET/POST` | `/conversations` | List or create conversations |
| `GET/PATCH/DELETE` | `/conversations/{id}` | Read, rename, or delete a conversation |
| `POST` | `/conversations/{id}/messages/stream` | Run a turn and replay buffered text |

The stream response includes `X-Stream-Mode: buffered` and `X-Request-Id`. It replays an already-completed answer rather than forwarding live provider tokens.

## Runtime Contracts

### Providers

`ModelProvider` exposes normalized `generate()` and `stream()` methods. `create_model_provider()` selects:

| Provider | Configuration gate |
| --- | --- |
| Ollama | `OLLAMA_MODEL` |
| OpenAI | `OPENAI_API_KEY` |
| Bedrock | `BEDROCK_MODEL_ID` and AWS credentials |

### Agents and Tools

The agent registry merges the supervisor, configured connector agents, and SQLite-backed custom agents. The tool registry merges static tools, configured connectors, and one generated tool per imported dataset.

Supervisor-only tools (`summarize_findings` and `build_chart_spec`) are hidden from custom-agent assignment. Dataset tools query the request-bound SQLite connection for metadata and read CSV content from disk.

### Supervisor

1. Ask the provider to select allowed specialist ids.
2. Validate the response or use keyword fallback routing.
3. Run specialists in stable order with explicit handoffs.
4. Run summary or chart follow-ups when needed.
5. Ask the provider to synthesize one final response.
6. Return the answer, specialist results, events, and artifacts.

Connector tools use model-generated arguments. Dataset tools currently fall back to inferred defaults such as `{ "limit": 50 }`.

### Persistence and Failure Behavior

`ChatTurnService` completes supervisor execution before changing conversation history. Provider configuration errors return 400; provider execution errors return 503 without appending turn messages.

After a successful supervisor run, the service writes the optional title, messages, artifacts, and events sequentially. Storage helpers commit independently, so a later database failure can leave earlier records in place.

## Key Invariants

1. Persisted conversation agent ids begin with `supervisor`.
2. Configured connector agents are injected during conversation normalization.
3. Provider selection is global to the backend process, not per agent.
4. Unknown custom-agent tools are rejected.
5. Deleting a conversation cascades its messages, events, artifacts, and legacy traces.
6. Deleting a dataset removes its file and generated tool registration.
7. Inspect data is available after the buffered turn completes.
