# End-to-End Test Scenarios

These scenarios exercise ChatRoom through its public UI and HTTP boundaries. They use the bundled mock services and synthetic sample data, so no paid provider or business credentials are required beyond a locally available Ollama model.

## 1. Test environment

Prerequisites:

- Python 3.11 or newer and `uv`
- Node.js matching `frontend/.nvmrc` and npm
- Ollama running with the model configured by `OLLAMA_MODEL`

Create the local configuration:

```sh
cp .env.example .env
```

For the complete connector path, enable the mock values documented in [`mock_services/README.md`](../mock_services/README.md), then start four processes from the repository root:

```sh
./mock_services/start_external_api.sh
./mock_services/start_snowflake_mock.sh
```

```sh
cd backend
uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

```sh
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

Open `http://127.0.0.1:5173`. Confirm `http://127.0.0.1:8001/health` reports `ollama` and that the model is available before continuing.

## 2. Baseline application health

1. Load the UI in a fresh browser session.
2. Confirm the sidebar, empty chat state, model selector, Settings, and Inspect controls render.
3. Open the model selector and confirm Ollama, OpenAI, and Bedrock are listed.
4. Open Settings and confirm connector readiness matches `.env`.
5. Open Inspect → Tools and confirm only configured tools are shown.

Expected result: the UI loads without console errors, the backend health endpoint is reachable, and unavailable providers/connectors explain their missing configuration.

## 3. Supervisor-only conversation

Run this scenario with connector settings disabled and no custom agents.

1. Select Ollama.
2. Start a new chat.
3. Send: `Explain what this application can do in three bullets.`
4. Wait for the answer, then reload the page and reopen the conversation.

Expected result:

- A conversation is created automatically and its title is derived from the first prompt.
- The answer renders as buffered chunks and survives reload.
- Inspect → Trace contains `manager_started` and `final_answer` events.
- The persisted team starts with `supervisor`.

## 4. Account-directory connector

Enable and start the external API mock.

1. Start a new chat.
2. Send: `Look up account AC-1001 and tell me its segment and status.`
3. Open Inspect → Trace.

Expected result:

- The manager selects the Account directory specialist.
- `lookup_account` is called with `AC-1001`.
- Trace contains `specialist_selected`, `tool_called`, `tool_finished`, `specialist_answered`, and `final_answer`.
- The final response agrees with `mock_services/external_api/accounts.json`.

## 5. Sales-pipeline connector and chart

Enable and start the Snowflake mock.

1. Start a new chat.
2. Send: `Summarize Closed Won revenue by region and create a chart.`
3. Inspect Trace and Artifacts.

Expected result:

- The Sales pipeline specialist runs `query_snowflake` with one read-only `SELECT` statement.
- The supervisor produces a synthesized answer grounded in returned rows.
- Inspect → Artifacts renders a chart specification with a title and data series.
- Reloading the conversation preserves both trace events and the artifact.

## 6. CSV knowledge and custom agent

1. Open Settings → Create knowledge base.
2. Upload `samples/student_grades.csv` with the name `Student grades`.
3. Confirm a `query_dataset_*` tool appears.
4. Open Create agent and create `Grade analyst` with clear analysis instructions and the uploaded dataset tool.
5. Start a new chat and send: `Compare average scores across the numeric subjects.`

Expected result:

- Dataset metadata and the custom agent survive a page reload.
- The manager may select `Grade analyst` and its dataset tool returns structured aggregates.
- The final answer uses the uploaded data rather than inventing values.
- Deleting the dataset removes its generated tool from Settings and `GET /tools`.

All records in `samples/student_grades.csv` are synthetic demonstration data.

## 7. Provider switching and readiness

1. Open the provider menu.
2. Select a provider without its required credentials.
3. Attempt to send a message.
4. Switch back to the configured Ollama provider and retry.

Expected result: provider health explains missing configuration, the unavailable-provider turn fails without appending user or assistant messages, and the configured provider completes the retry. Provider selection is global to the running backend process, not per conversation or user.

## 8. Conversation management

1. Create two conversations and send at least one message in each.
2. Rename one conversation.
3. Reload and confirm both names and histories.
4. Delete one conversation and reload again.

Expected result: renaming persists, deletion removes the conversation and its messages, events, and artifacts, and the remaining conversation is unaffected.

## 9. Failure and validation checks

Verify these negative cases through the UI or API:

| Action | Expected result |
| --- | --- |
| Upload an empty, non-CSV, or larger-than-2-MB dataset | HTTP 400 with a readable error |
| Create an agent with an unknown tool | HTTP 400 |
| Send to an unknown conversation id | HTTP 404 |
| Rename a conversation to whitespace | HTTP 400 |
| Ask the Snowflake tool to execute non-`SELECT` SQL | Tool rejects the statement |
| Stop the active model provider before sending | HTTP 503 and no new conversation messages |

Successful-turn database writes are sequential and commit independently. This test plan does not claim that an unexpected failure midway through persistence rolls back earlier records.

## 10. Automated regression checks

Run the existing checks before a release:

```sh
cd backend
uv run pytest
```

```sh
cd frontend
npm run lint
npm run build
```

Live-provider smoke tests are skipped unless explicitly enabled with the environment variables documented in `backend/tests/test_live_provider_smoke.py`.
