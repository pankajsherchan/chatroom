# Mock Services and Data

Local services and synthetic data for demonstrating connector and CSV-agent workflows without production credentials.

| Resource | Location | Purpose |
| --- | --- | --- |
| Account API | `external_api/` on port `8010` | Powers `lookup_account` |
| Snowflake mock | `snowflake_mock/` on port `8011` | Powers `query_snowflake` |
| Student grades | `data/student_grades.csv` | Upload example for a custom CSV agent |

## Start

Run from the repository root in separate terminals:

```sh
./mock_services/start_external_api.sh
```

```sh
./mock_services/start_snowflake_mock.sh
```

Add this local-only configuration to `.env`, then restart the backend:

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

Health checks:

```sh
curl http://127.0.0.1:8010/health
curl http://127.0.0.1:8011/health
```

Settings and Inspect should now show the Account directory and Sales pipeline tools. Upload `mock_services/data/student_grades.csv` through Create knowledge base to try a custom data agent.

## Data and Overrides

- Account records: `external_api/accounts.json`
- Pipeline records: `snowflake_mock/data/pipeline_deals.csv`
- CSV upload example: `data/student_grades.csv`
- `MOCK_EXTERNAL_API_PORT` and `MOCK_EXTERNAL_API_KEY` override account-service defaults.
- `MOCK_SNOWFLAKE_PORT`, `MOCK_SNOWFLAKE_CSV`, and `MOCK_SNOWFLAKE_TABLE` override Snowflake-mock defaults.

All bundled records and credentials are synthetic and intended only for local development.
