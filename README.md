# ChatRoom

ChatRoom is a local-first multi-agent chat platform that coordinates a supervisor and specialized agents to answer questions with model reasoning, structured tools, and connected data.

It demonstrates an end-to-end agentic application rather than a standalone chatbot: the supervisor selects the smallest useful specialist team, specialists query approved tools, and the supervisor synthesizes one response. The application preserves conversations, execution traces, and generated artifacts so every turn can be inspected after it runs.

Built with React, TypeScript, FastAPI, Python, and SQLite, ChatRoom supports local Ollama models as well as OpenAI and Amazon Bedrock. Bundled mock services make the connector workflows reproducible without access to production systems.

## Key Capabilities

- **ChatGPT-style UI** — dark sidebar, conversation history, centered chat, Settings modal, Inspect panel
- **Supervisor orchestration** — provider-driven specialist selection with deterministic routing fallback
- **Specialized agents and tools** — configurable agents with constrained tool access and explicit handoffs
- **Pluggable model providers** — Ollama, OpenAI, and Amazon Bedrock behind a shared provider interface
- **Connected data** — Snowflake and external account APIs, with bundled local mock services
- **CSV knowledge tools** — uploaded datasets become query tools assignable to custom agents
- **Inspectable execution** — persisted routing decisions, tool calls, specialist findings, and chart artifacts
- **Local persistence** — SQLite-backed conversations, messages, custom agents, datasets, and traces
- **Automated backend coverage** — 190 passing tests across APIs, storage, providers, connectors, tools, and orchestration

## Architecture and Testing

- [High-Level Design](docs/high_level_design.md) — architecture, concepts, process flows
- [Low-Level Design](docs/low_level_design.md) — DB schema, API catalog, module contracts, E2E checklist
- [E2E test scenarios](docs/e2e_test_scenarios.md) — step-by-step UI / API / DB / Inspect checks
- [Group chat flow](docs/local_group_chat_flow.md) — one-turn Mermaid sequence

```text
chatroom/
├── .env.example
├── backend/
│   ├── app/          # FastAPI, supervisor, connectors, providers
│   ├── tools/        # Local tool implementations
│   └── tests/
├── docs/
├── frontend/src/     # ChatGPT-style React UI
├── mock_services/    # Optional local Snowflake + account API mocks
└── README.md
```



## Prerequisites

- Python 3.11+
- `uv`
- Node.js 20.19+ or 22.12+ (see `frontend/.nvmrc`)
- npm
- For real chat: [Ollama](https://ollama.com) with a pulled model (for example `llama3.2`)



## First Run

```sh
cd chatroom
cp .env.example .env
```

Recommended `.env` defaults use **Ollama**:

```env
MODEL_PROVIDER=ollama
OLLAMA_MODEL=llama3.2
```



### Run The App

Two terminals:

**Backend**

```sh
cd chatroom/backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

**Frontend**

```sh
cd chatroom/frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173).

### First Useful Chat

1. Start the optional connectors if you want Sales pipeline / Account directory (see `mock_services/README.md`).
2. Open **Settings** (sidebar footer):
  - **Create agent** → Agent Studio; pick **Available tools** (connectors + CSV tools)
  - **Create knowledge base** → upload CSVs as `query_dataset_`* tools
  - **Your agents** — custom specialists with one or more tools (backend connectors and/or CSV knowledge)
3. Type a message and send. The app creates a conversation automatically.
4. Open **Inspect** for routing, tool calls, and charts.

Built-in connector agents are included automatically when configured. Custom agents are included when you have any. You do **not** need a custom agent for Snowflake or account lookup — those are tools used by the built-in specialists.

## Optional Mock Connectors

```sh
./mock_services/start_external_api.sh
./mock_services/start_snowflake_mock.sh
```

Add the sample values from `mock_services/README.md` to `.env`, restart the backend, then open **Settings → Create agent** and confirm Sales pipeline / Account directory appear under Available tools.

## Turn Reports (optional HTML after each chat)

Turn reports are **opt-in**. Set `TURN_REPORTS_ENABLED=1` to write reviewable reports under `backend/data/turn_reports/`:

- `.html` — flowchart-style page with manager → specialist → tool → final answer
- `.json` — same payload for tooling (secret-like fields are redacted)

Watch the backend terminal for:

```text
[turn-report] /.../backend/data/turn_reports/....html
```

Or open the newest file in that folder after sending a message.
## Verification

```sh
cd backend && uv run pytest
cd frontend && npm run lint && npm run build
```



## What To Inspect First

1. `docs/high_level_design.md` — system shape and flows
2. `docs/low_level_design.md` — schema, endpoints, invariants
3. `backend/app/main.py` — FastAPI entrypoint
4. `backend/app/api/conversations.py` — chat HTTP routes
5. `backend/app/services/chat_turn.py` — provider-first turn orchestration + sequential persistence
6. `backend/app/supervisor/` — `ProviderSupervisor`, specialists, follow-ups
7. `backend/app/connector_agents.py` — built-in Sales pipeline / Account directory agents
8. `backend/app/tool_registry.py` — static, connector, and dataset tools
9. `frontend/src/App.tsx` — UI shell
10. `docs/local_group_chat_flow.md` — one chat-turn diagrams



## Request Flow Walkthrough

`ChatTurnService` runs `ProviderSupervisor` before changing conversation history. On success, it writes the title, messages, artifacts, and Inspect events in sequence, then replays the answer as buffered text. Provider failures happen before those writes, so they do not leave an orphan user message. The successful-turn writes are not wrapped in one atomic database transaction.

See the [high-level process flows](docs/high_level_design.md#5-end-to-end-process-flows), [group chat sequence](docs/local_group_chat_flow.md), and [stream contract](docs/low_level_design.md#35-conversations--chat) for details.

## Provider Abstraction


| Provider  | In UI? | Required config                      |
| --------- | ------ | ------------------------------------ |
| `ollama`  | Yes    | `OLLAMA_MODEL`                       |
| `openai`  | Yes    | `OPENAI_API_KEY`                     |
| `bedrock` | Yes    | `BEDROCK_MODEL_ID` + AWS credentials |


Switch the active provider from the sidebar model menu (`PUT /providers/active`). Chat uses the provider for supervisor routing via `generate()`, not a full per-agent tool-call loop yet.

## Tools


| Source          | Examples                                 | When available                                                |
| --------------- | ---------------------------------------- | ------------------------------------------------------------- |
| Supervisor-only | `summarize_findings`, `build_chart_spec` | Always; hidden from agent assignment                          |
| CSV upload      | `query_dataset_*`                        | After Settings → Create knowledge base                        |
| Snowflake       | `query_snowflake`                        | When `SNOWFLAKE_*` is set (Sales pipeline agent)              |
| External API    | `lookup_account`                         | When `EXTERNAL_API_BASE_URL` is set (Account directory agent) |




## Supervisor Group Chat

Local `ProviderSupervisor` lets a manager pick specialists, run tools, and produce one synthesized answer.

## Next Changes To Try

1. Upload a CSV and create a custom agent that uses its query tool.
2. Register a new `LocalTool` under `backend/tools/` and write a unit test.
3. Enable mock connectors and ask about revenue by region or account `AC-1001`.
4. Switch providers from the sidebar and use Inspect → Trace.
5. Extend provider-driven tool selection to dataset tools.



## Known Limitations

- Snowflake and lookup_account use model tool calls; dataset tools still use inferred `{limit: 50}` arguments.
- The `/messages/stream` endpoint replays a completed answer as buffered chunks; it is not live provider-token streaming.
- Local RAG is planned for P2.
