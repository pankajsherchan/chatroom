"""Optional Snowflake SQL local tool."""

from app.connectors.snowflake import execute_snowflake_query
from tools.base import LocalTool, ParameterSchema, ToolArguments, ToolOutput


QUERY_SNOWFLAKE_PARAMETER_SCHEMA: ParameterSchema = {
    "type": "object",
    "properties": {
        "sql": {
            "type": "string",
            "description": "Read-only Snowflake SELECT statement to execute.",
        },
        "max_rows": {
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
            "description": "Maximum rows to return when the SQL has no LIMIT clause.",
        },
    },
    "required": ["sql"],
}


def run_query_snowflake(arguments: ToolArguments) -> ToolOutput:
    sql = _sql_argument(arguments)
    max_rows = _max_rows_argument(arguments)
    return execute_snowflake_query(sql, max_rows=max_rows)


QUERY_SNOWFLAKE_TOOL = LocalTool(
    name="query_snowflake",
    description=(
        "Run a read-only SELECT query against the configured Snowflake warehouse. "
        "Only available when Snowflake credentials are present."
    ),
    parameter_schema=QUERY_SNOWFLAKE_PARAMETER_SCHEMA,
    run=run_query_snowflake,
)


def _sql_argument(arguments: ToolArguments) -> str:
    value = arguments.get("sql")
    if not isinstance(value, str) or value.strip() == "":
        raise ValueError("sql must be a non-empty string.")
    return value.strip()


def _max_rows_argument(arguments: ToolArguments) -> int:
    if "max_rows" not in arguments or arguments.get("max_rows") is None:
        return 100

    value = arguments["max_rows"]
    if isinstance(value, bool):
        raise ValueError("max_rows must be an integer.")
    if isinstance(value, int):
        coerced = value
    elif isinstance(value, float) and value.is_integer():
        coerced = int(value)
    elif isinstance(value, str) and value.strip().isdigit():
        coerced = int(value.strip())
    else:
        raise ValueError(
            f"max_rows must be an integer. got {type(value).__name__}={value!r}"
        )

    if coerced < 1 or coerced > 100:
        raise ValueError("max_rows must be between 1 and 100.")
    return coerced
