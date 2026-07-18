from collections.abc import Iterable, Sequence
from unittest.mock import patch

from app.agents import LocalAgent
from app.connectors.external_api import set_http_transport
from app.models.supervisor import SupervisorRequest
from app.providers import ModelMessage, ModelResponse, ToolCall, ToolSpec
from app.supervisor import ProviderSupervisor
from tests.test_external_api_connector import FakeHttpTransport, _settings


REGION_REVENUE_SQL = (
    "SELECT region, SUM(CAST(revenue AS REAL)) AS total_revenue "
    "FROM pipeline_deals WHERE stage = 'Closed Won' "
    "GROUP BY region LIMIT 10"
)
DEAL_LOOKUP_SQL = (
    "SELECT deal_id, close_month, region, segment, product_line, stage, owner, "
    "revenue, probability_pct FROM pipeline_deals WHERE deal_id = 'D-2001' LIMIT 10"
)
EXPLICIT_SQL = "SELECT region FROM pipeline_deals LIMIT 3"


class RoutingProvider:
    def __init__(
        self,
        content: str,
        tool_calls: Sequence[ToolCall] = (),
    ) -> None:
        self.content = content
        self.tool_calls = tuple(tool_calls)
        self.generate_calls: list[Sequence[ModelMessage]] = []
        self.tools_seen: list[list[ToolSpec]] = []

    def generate(
        self,
        messages: Sequence[ModelMessage],
        *,
        tools: Sequence[ToolSpec] = (),
    ) -> ModelResponse:
        self.generate_calls.append(messages)
        self.tools_seen.append(list(tools))
        # Manager / final-answer calls have no tools.
        if not tools:
            return ModelResponse(content=self.content)
        # Specialist tool-calling turn.
        return ModelResponse(content="", tool_calls=self.tool_calls)

    def stream(
        self,
        messages: Sequence[ModelMessage],
        *,
        tools: Sequence[ToolSpec] = (),
    ) -> Iterable[str]:
        return iter(())


def _run_with_fallback(
    request: SupervisorRequest,
    *,
    tool_calls: Sequence[ToolCall] = (),
) -> tuple[object, RoutingProvider]:
    """Use an invalid provider choice so routing falls back to local rules."""

    provider = RoutingProvider(
        '{"agent_ids": ["unknown_agent"]}',
        tool_calls=tool_calls,
    )
    return ProviderSupervisor(provider).run(request), provider


def test_provider_supervisor_lists_all_accounts_without_account_id():
    settings = _settings()
    transport = FakeHttpTransport()
    tool_calls = (ToolCall(name="lookup_account", arguments={}),)

    with patch("app.tool_registry.get_settings", return_value=settings), patch(
        "app.connectors.external_api.get_settings", return_value=settings
    ):
        set_http_transport(transport)
        custom_agent = LocalAgent(
            id="custom_account",
            name="Account Helper",
            description="Looks up business accounts.",
            system_prompt="Use the external account API.",
            tools=("lookup_account",)
        )
        request = SupervisorRequest(
            selected_agent_ids=(custom_agent.id,),
            messages=(),
            user_input="show the look up data",
            agent_catalog={custom_agent.id: custom_agent},
        )

        response, provider = _run_with_fallback(request, tool_calls=tool_calls)

    assert response.content == (
        "Found 2 accounts:\n"
        "- AC-1001: Northwind Traders (Enterprise, status=active)\n"
        "- AC-1002: Contoso Retail (Mid-Market, status=active)"
    )
    assert any(tools for tools in provider.tools_seen)


@patch("app.tool_registry.get_settings")
@patch("app.connectors.external_api.get_settings")
def test_provider_supervisor_runs_lookup_account_from_provider_tool_call(
    mock_external_settings,
    mock_registry_settings,
):
    settings = _settings()
    mock_external_settings.return_value = settings
    mock_registry_settings.return_value = settings
    set_http_transport(FakeHttpTransport())
    tool_calls = (
        ToolCall(name="lookup_account", arguments={"account_id": "AC-1001"}),
    )

    custom_agent = LocalAgent(
        id="custom_account",
        name="Account Helper",
        description="Looks up business accounts.",
        system_prompt="Use the external account API.",
        tools=("lookup_account",)
    )
    request = SupervisorRequest(
        selected_agent_ids=(custom_agent.id,),
        messages=(),
        user_input="Look up account AC-1001 for me",
        agent_catalog={custom_agent.id: custom_agent},
    )

    response, provider = _run_with_fallback(request, tool_calls=tool_calls)

    assert response.content == (
        "Account AC-1001 is Northwind Traders (Enterprise, status=active)."
    )
    assert any(tools for tools in provider.tools_seen)


def test_provider_supervisor_skips_lookup_account_without_provider_tool_call():
    settings = _settings()

    with patch("app.tool_registry.get_settings", return_value=settings), patch(
        "app.connectors.external_api.get_settings", return_value=settings
    ):
        set_http_transport(FakeHttpTransport())
        custom_agent = LocalAgent(
            id="custom_account",
            name="Account Helper",
            description="Looks up business accounts.",
            system_prompt="Use the external account API.",
            tools=("lookup_account",)
        )
        request = SupervisorRequest(
            selected_agent_ids=(custom_agent.id,),
            messages=(),
            user_input="Look up account AC-1001 for me",
            agent_catalog={custom_agent.id: custom_agent},
        )

        response, provider = _run_with_fallback(request)

    assert any(tools for tools in provider.tools_seen)
    assert "Skipped lookup_account" in response.agent_results[0].content


def test_provider_supervisor_runs_snowflake_query_from_provider_tool_call():
    settings = _settings(
        snowflake_account="local",
        snowflake_user="mock",
        snowflake_password="mock",
        snowflake_warehouse="MOCK_WH",
        snowflake_database="MOCK_DB",
        snowflake_schema="PUBLIC",
    )
    tool_calls = (
        ToolCall(
            name="query_snowflake",
            arguments={"sql": REGION_REVENUE_SQL, "max_rows": 10},
        ),
    )

    with patch("app.tool_registry.get_settings", return_value=settings), patch(
        "app.connectors.snowflake.get_settings", return_value=settings
    ), patch("app.connectors.snowflake._execute_local_mock") as mock_execute:
        mock_execute.return_value = {
            "sql": REGION_REVENUE_SQL,
            "columns": ["region", "total_revenue"],
            "row_count": 2,
            "rows": [
                {"region": "West", "total_revenue": 100.0},
                {"region": "East", "total_revenue": 200.0},
            ],
        }
        custom_agent = LocalAgent(
            id="custom_snowflake",
            name="Snowflake Analyst",
            description="Runs Snowflake queries.",
            system_prompt="Use Snowflake for analytics.",
            tools=("query_snowflake",)
        )
        request = SupervisorRequest(
            selected_agent_ids=(custom_agent.id,),
            messages=(),
            user_input="show revenue by region",
            agent_catalog={custom_agent.id: custom_agent},
        )

        response, provider = _run_with_fallback(request, tool_calls=tool_calls)

    assert response.content.startswith("Returned 2 rows:")
    assert "region=West" in response.content
    assert any(tools for tools in provider.tools_seen)
    assert mock_execute.call_args[0][2] == REGION_REVENUE_SQL
    mock_execute.assert_called_once()


def test_provider_supervisor_runs_snowflake_deal_lookup_from_provider_tool_call():
    settings = _settings(
        snowflake_account="local",
        snowflake_user="mock",
        snowflake_password="mock",
        snowflake_warehouse="MOCK_WH",
        snowflake_database="MOCK_DB",
        snowflake_schema="PUBLIC",
    )
    tool_calls = (
        ToolCall(
            name="query_snowflake",
            arguments={"sql": DEAL_LOOKUP_SQL, "max_rows": 10},
        ),
    )

    with patch("app.tool_registry.get_settings", return_value=settings), patch(
        "app.connectors.snowflake.get_settings", return_value=settings
    ), patch("app.connectors.snowflake._execute_local_mock") as mock_execute:
        mock_execute.return_value = {
            "sql": DEAL_LOOKUP_SQL,
            "columns": [
                "deal_id",
                "close_month",
                "region",
                "segment",
                "product_line",
                "stage",
                "owner",
                "revenue",
                "probability_pct",
            ],
            "row_count": 1,
            "rows": [
                {
                    "deal_id": "D-2001",
                    "close_month": "2026-01",
                    "region": "West",
                    "segment": "Enterprise",
                    "product_line": "Analytics Platform",
                    "stage": "Closed Won",
                    "owner": "Alex Chen",
                    "revenue": "48000",
                    "probability_pct": "100",
                }
            ],
        }
        custom_agent = LocalAgent(
            id="custom_snowflake",
            name="Snowflake Analyst",
            description="Runs Snowflake queries.",
            system_prompt="Use Snowflake for analytics.",
            tools=("query_snowflake",)
        )
        request = SupervisorRequest(
            selected_agent_ids=(custom_agent.id,),
            messages=(),
            user_input="show me data for D-2001",
            agent_catalog={custom_agent.id: custom_agent},
        )

        response, provider = _run_with_fallback(request, tool_calls=tool_calls)

    assert response.content == (
        "Deal D-2001: Analytics Platform in West "
        "(Closed Won, revenue=48000, owner=Alex Chen)."
    )
    assert any(tools for tools in provider.tools_seen)
    assert mock_execute.call_args[0][2] == DEAL_LOOKUP_SQL


def test_provider_supervisor_runs_snowflake_sql_from_provider_tool_call():
    settings = _settings(
        snowflake_account="local",
        snowflake_user="mock",
        snowflake_password="mock",
        snowflake_warehouse="MOCK_WH",
        snowflake_database="MOCK_DB",
        snowflake_schema="PUBLIC",
    )
    tool_calls = (
        ToolCall(
            name="query_snowflake",
            arguments={"sql": EXPLICIT_SQL, "max_rows": 10},
        ),
    )

    with patch("app.tool_registry.get_settings", return_value=settings), patch(
        "app.connectors.snowflake.get_settings", return_value=settings
    ), patch("app.connectors.snowflake._execute_local_mock") as mock_execute:
        mock_execute.return_value = {
            "sql": EXPLICIT_SQL,
            "columns": ["region"],
            "row_count": 3,
            "rows": [
                {"region": "West"},
                {"region": "East"},
                {"region": "Central"},
            ],
        }
        custom_agent = LocalAgent(
            id="custom_snowflake",
            name="Snowflake Analyst",
            description="Runs Snowflake queries when SQL is available.",
            system_prompt="Use Snowflake for warehouse analytics.",
            tools=("query_snowflake",)
        )
        request = SupervisorRequest(
            selected_agent_ids=(custom_agent.id,),
            messages=(),
            user_input="SELECT region FROM pipeline_deals LIMIT 3",
            agent_catalog={custom_agent.id: custom_agent},
        )

        response, provider = _run_with_fallback(request, tool_calls=tool_calls)

    assert response.content.startswith("Returned 3 rows:")
    assert "region=West" in response.content
    assert any(tools for tools in provider.tools_seen)
    assert mock_execute.call_args[0][2] == EXPLICIT_SQL


def test_provider_supervisor_skips_snowflake_without_provider_tool_call():
    settings = _settings(
        snowflake_account="local",
        snowflake_user="mock",
        snowflake_password="mock",
        snowflake_warehouse="MOCK_WH",
        snowflake_database="MOCK_DB",
        snowflake_schema="PUBLIC",
    )

    with patch("app.tool_registry.get_settings", return_value=settings), patch(
        "app.connectors.snowflake.get_settings", return_value=settings
    ), patch("app.connectors.snowflake._execute_local_mock") as mock_execute:
        custom_agent = LocalAgent(
            id="custom_snowflake",
            name="Snowflake Analyst",
            description="Runs Snowflake queries.",
            system_prompt="Use Snowflake for analytics.",
            tools=("query_snowflake",)
        )
        request = SupervisorRequest(
            selected_agent_ids=(custom_agent.id,),
            messages=(),
            user_input="show revenue by region",
            agent_catalog={custom_agent.id: custom_agent},
        )

        response, provider = _run_with_fallback(request)

    assert any(tools for tools in provider.tools_seen)
    mock_execute.assert_not_called()
    assert "Skipped query_snowflake" in response.agent_results[0].content
