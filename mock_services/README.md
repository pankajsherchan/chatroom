# Local mock external services

Small standalone HTTP servers for trying optional connectors without real Snowflake or business-system credentials.

## What is included

| Service | Port | Used by |
| --- | --- | --- |
| `external_api` | `8010` | `lookup_account` via `EXTERNAL_API_BASE_URL` |
| `snowflake_mock` | `8011` | `query_snowflake` when `SNOWFLAKE_ACCOUNT=local` |

Both services reuse the backend virtualenv (`fastapi`, `uvicorn`).

## Start the mocks

Terminal 1:

```sh
cd chatroom
./mock_services/start_external_api.sh
```

Terminal 2:

```sh
cd chatroom
./mock_services/start_snowflake_mock.sh
```

Health checks:

```sh
curl http://127.0.0.1:8010/health
curl http://127.0.0.1:8011/health
```

## Wire the main app

Add these values to `chatroom/.env`:

```env
EXTERNAL_API_BASE_URL=http://127.0.0.1:8010
EXTERNAL_API_KEY=dev-token

SNOWFLAKE_ACCOUNT=local
SNOWFLAKE_USER=mock
SNOWFLAKE_PASSWORD=mock
SNOWFLAKE_WAREHOUSE=MOCK_WH
SNOWFLAKE_DATABASE=MOCK_DB
SNOWFLAKE_SCHEMA=PUBLIC
SNOWFLAKE_MOCK_URL=http://127.0.0.1:8011
```

Restart the backend on port `8001`, then:

- **Settings → Create agent → Available options** should show Sales pipeline and Account directory as ready
- **Inspect → Tools** should list `lookup_account` and `query_snowflake`

## Try the mocks directly

External account lookup:

```sh
curl -H "Authorization: Bearer dev-token" http://127.0.0.1:8010/accounts/AC-1001

curl -H "Authorization: Bearer dev-token" http://127.0.0.1:8010/accounts
```

Mock Snowflake SQL:

```sh
curl -X POST http://127.0.0.1:8011/query \
  -H 'Content-Type: application/json' \
  -d '{"sql":"SELECT region, SUM(CAST(revenue AS REAL)) AS total_revenue FROM pipeline_deals WHERE stage = '\''Closed Won'\'' GROUP BY region LIMIT 5"}'
```

## Mock data

- External API accounts live in `mock_services/external_api/accounts.json`
- Snowflake mock loads `mock_services/snowflake_mock/data/pipeline_deals.csv` into a `pipeline_deals` table

## Optional mock server env vars

External API mock:

- `MOCK_EXTERNAL_API_PORT` (default `8010`)
- `MOCK_EXTERNAL_API_KEY` (default `dev-token`)

Snowflake mock:

- `MOCK_SNOWFLAKE_PORT` (default `8011`)
- `MOCK_SNOWFLAKE_CSV` (default `mock_services/snowflake_mock/data/pipeline_deals.csv`)
- `MOCK_SNOWFLAKE_TABLE` (optional override; defaults to the CSV filename stem)
