from collections.abc import Iterable, Sequence
from unittest.mock import patch

import pytest

from app.agents import LocalAgent
from app.providers import ModelMessage, ModelResponse, ToolCall, ToolSpec
from app.models.supervisor import (
    AgentRunResult,
    AgentHandoffRequest,
    SupervisorRequest,
    SupervisorResponse,
)
from app.routing import route_agent_ids
from app.supervisor import (
    ProviderSupervisor,
    Supervisor,
)
from app.connectors.external_api import set_http_transport
from app.connectors.snowflake import set_snowflake_executor
from tests.test_external_api_connector import FakeHttpTransport, _settings


class EchoSupervisor:
    def __init__(self) -> None:
        self.requests: list[SupervisorRequest] = []

    def run(self, request: SupervisorRequest) -> SupervisorResponse:
        self.requests.append(request)
        return SupervisorResponse(
            content=f"supervised: {request.user_input}",
            agent_results=(
                AgentRunResult(agent_id=request.selected_agent_ids[0], content="planned"),
            ),
        )


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
        if not tools:
            return ModelResponse(content=self.content)
        return ModelResponse(content="", tool_calls=self.tool_calls)

    def stream(
        self,
        messages: Sequence[ModelMessage],
        *,
        tools: Sequence[ToolSpec] = (),
    ) -> Iterable[str]:
        return iter(())


def test_supervisor_request_captures_selected_agents_messages_and_user_input():
    messages = [
        ModelMessage(role="user", content="Earlier question"),
        ModelMessage(role="assistant", content="Earlier answer"),
    ]

    request = SupervisorRequest(
        selected_agent_ids=["custom_test"],
        messages=messages,
        user_input="Show revenue by region.",
    )

    assert request.selected_agent_ids == ("custom_test",)
    assert request.messages == tuple(messages)
    assert request.user_input == "Show revenue by region."


def test_supervisor_protocol_runs_request_and_returns_response():
    supervisor: Supervisor = EchoSupervisor()
    request = SupervisorRequest(
        selected_agent_ids=("custom_test",),
        messages=(),
        user_input="Make a plan.",
    )

    response = supervisor.run(request)

    assert response.content == "supervised: Make a plan."
    assert response.called_agent_ids == ("custom_test",)


def test_agent_run_result_can_carry_tool_outputs():
    result = AgentRunResult(
        agent_id="custom_test",
        content="Revenue was 100.",
        tool_outputs=[{"tool_name": "query_snowflake", "row_count": 1}],
    )

    assert result.tool_outputs == (
        {"tool_name": "query_snowflake", "row_count": 1},
    )


def test_agent_handoff_request_captures_delegation_details():
    context = (
        ModelMessage(role="user", content="Earlier question"),
        ModelMessage(role="assistant", content="Earlier answer", agent_name="supervisor"),
    )

    request = AgentHandoffRequest(
        original_user_input="Summarize revenue by channel.",
        context=context,
        target_agent_id="summarizer",
        specific_request="Summarize the available findings.",
    )

    assert request.original_user_input == "Summarize revenue by channel."
    assert request.context == context
    assert request.target_agent_id == "summarizer"
    assert request.specific_request == "Summarize the available findings."


def test_agent_run_result_can_carry_handoff_request():
    handoff_request = AgentHandoffRequest(
        original_user_input="Show revenue.",
        context=(),
        target_agent_id="custom_test",
        specific_request="Use configured tools.",
    )

    result = AgentRunResult(
        agent_id="custom_test",
        content="Revenue was 100.",
        handoff_request=handoff_request,
    )

    assert result.handoff_request == handoff_request


def test_supervisor_response_tracks_agent_results_and_artifacts():
    agent_results: Sequence[AgentRunResult] = [
        AgentRunResult(agent_id="visualizer", content="Built a chart.")
    ]
    artifacts = [{"type": "chart", "title": "Revenue by region"}]

    response = SupervisorResponse(
        content="Here is the chart.",
        agent_results=agent_results,
        artifacts=artifacts,
    )

    assert response.called_agent_ids == ("visualizer",)
    assert response.artifacts == ({"type": "chart", "title": "Revenue by region"},)


def test_route_agent_ids_returns_empty_without_custom_agents():
    request = SupervisorRequest(
        selected_agent_ids=("supervisor",),
        messages=(),
        user_input="What was total revenue by region?",
    )

    assert route_agent_ids(request) == ()


def test_route_agent_ids_routes_to_selected_custom_agent():
    custom_agent = LocalAgent(
        id="custom_test",
        name="Snowflake Analyst",
        description="Runs Snowflake queries.",
        system_prompt="Use Snowflake.",
        tools=("query_snowflake",)
    )
    request = SupervisorRequest(
        selected_agent_ids=(custom_agent.id,),
        messages=(),
        user_input="show revenue by region",
        agent_catalog={custom_agent.id: custom_agent},
    )

    assert route_agent_ids(request) == (custom_agent.id,)


def test_provider_supervisor_reports_no_selection_without_custom_agents():
    provider = RoutingProvider('{"agent_ids": ["unknown_agent"]}')
    response = ProviderSupervisor(provider).run(
        SupervisorRequest(
            selected_agent_ids=("supervisor",),
            messages=(),
            user_input="What was total revenue by region?",
        )
    )

    assert response.content == "No specialist agents were selected."
    assert response.called_agent_ids == ()


def test_provider_supervisor_runs_summarize_follow_up_for_custom_agent():
    settings = _settings(
        snowflake_account="local",
        snowflake_user="mock",
        snowflake_password="mock",
        snowflake_warehouse="MOCK_WH",
        snowflake_database="MOCK_DB",
        snowflake_schema="PUBLIC",
    )
    region_sql = (
        "SELECT region, SUM(CAST(revenue AS REAL)) AS total_revenue "
        "FROM pipeline_deals WHERE stage = 'Closed Won' GROUP BY region LIMIT 10"
    )
    custom_agent = LocalAgent(
        id="custom_snowflake",
        name="Snowflake Analyst",
        description="Runs Snowflake queries.",
        system_prompt="Use Snowflake.",
        tools=("query_snowflake",)
    )
    provider = RoutingProvider(
        '{"agent_ids": ["unknown_agent"]}',
        tool_calls=(
            ToolCall(
                name="query_snowflake",
                arguments={"sql": region_sql, "max_rows": 10},
            ),
        ),
    )

    with patch("app.tool_registry.get_settings", return_value=settings), patch(
        "app.connectors.snowflake.get_settings", return_value=settings
    ):
        set_snowflake_executor(None)
        with patch("app.connectors.snowflake._execute_local_mock") as mock_execute:
            mock_execute.return_value = {
                "sql": region_sql,
                "columns": ["region", "total_revenue"],
                "row_count": 3,
                "rows": [
                    {"region": "West", "total_revenue": 100.0},
                    {"region": "East", "total_revenue": 200.0},
                    {"region": "Central", "total_revenue": 150.0},
                ],
            }
            response = ProviderSupervisor(provider).run(
                SupervisorRequest(
                    selected_agent_ids=(custom_agent.id,),
                    messages=(),
                    user_input="show revenue by region and summarize as bullets",
                    agent_catalog={custom_agent.id: custom_agent},
                )
            )

    assert response.called_agent_ids == (custom_agent.id, "summarizer")
    assert "Matched 3 rows." in response.content
    assert any(tools for tools in provider.tools_seen)
    assert mock_execute.call_args[0][2] == region_sql


def test_provider_supervisor_falls_back_to_custom_agent_routing_for_invalid_choice():
    provider = RoutingProvider(
        '{"agent_ids": ["unknown_agent"]}',
        tool_calls=(
            ToolCall(name="lookup_account", arguments={"account_id": "AC-1001"}),
        ),
    )
    supervisor = ProviderSupervisor(provider)
    settings = _settings()
    custom_agent = LocalAgent(
        id="custom_test",
        name="Account Helper",
        description="Looks up business accounts.",
        system_prompt="Use the external account API.",
        tools=("lookup_account",)
    )
    request = SupervisorRequest(
        selected_agent_ids=(custom_agent.id,),
        messages=(),
        user_input="Look up account AC-1001",
        agent_catalog={custom_agent.id: custom_agent},
    )

    set_http_transport(FakeHttpTransport())
    with patch("app.tool_registry.get_settings", return_value=settings), patch(
        "app.connectors.external_api.get_settings", return_value=settings
    ):
        response = supervisor.run(request)

    assert response.called_agent_ids == (custom_agent.id,)
    assert "Account AC-1001 is Northwind Traders" in response.content
    assert any(tools for tools in provider.tools_seen)


def test_dataset_tool_output_is_readable_in_synthesis() -> None:
    from app.supervisor import _synthesize_agent_results

    result = AgentRunResult(
        agent_id="custom_student",
        content="internal log should be ignored when tool summary exists",
        tool_outputs=(
            {
                "tool_name": "query_dataset_students",
                "arguments": {"limit": 50},
                "output": {
                    "row_count": 3,
                    "filters": {},
                    "group_by": None,
                    "average_gpa": 8.9,
                    "average_math": 90.0,
                    "rows": [
                        {
                            "student_id": "S-1",
                            "student_name": "Ava Chen",
                            "gpa": 9.1,
                            "math": 92.0,
                        },
                        {
                            "student_id": "S-2",
                            "student_name": "Olivia Rahman",
                            "gpa": 9.3,
                            "math": 96.0,
                        },
                        {
                            "student_id": "S-3",
                            "student_name": "Liam Nguyen",
                            "gpa": 7.5,
                            "math": 67.0,
                        },
                    ],
                },
            },
        ),
    )

    content = _synthesize_agent_results([result])

    assert "Supervisor synthesized results from" not in content
    assert "Matched 3 rows from the knowledge base." in content
    assert "Averages: gpa=8.9" in content
    assert "Highest gpa among returned rows: 9.3 (Olivia Rahman)." in content
    assert "student_name=Olivia Rahman" in content


def test_provider_supervisor_uses_llm_final_answer_from_tool_evidence() -> None:
    class TwoStepProvider:
        def __init__(self) -> None:
            self.generate_calls: list[Sequence[ModelMessage]] = []

        def generate(
            self,
            messages: Sequence[ModelMessage],
            *,
            tools: Sequence[ToolSpec] = (),
        ) -> ModelResponse:
            self.generate_calls.append(messages)
            if len(self.generate_calls) == 1:
                return ModelResponse(
                    content='{"agent_ids": ["custom_student"]}',
                )
            return ModelResponse(
                content="Olivia Rahman has the highest GPA at 9.3.",
            )

        def stream(
            self,
            messages: Sequence[ModelMessage],
            *,
            tools: Sequence[ToolSpec] = (),
        ) -> Iterable[str]:
            return iter(())

    provider = TwoStepProvider()
    custom_agent = LocalAgent(
        id="custom_student",
        name="student agent",
        description="Answers student grade questions.",
        system_prompt="Use the student grades dataset.",
        tools=(),
    )
    request = SupervisorRequest(
        selected_agent_ids=(custom_agent.id,),
        messages=(),
        user_input="Who has the highest GPA?",
        agent_catalog={custom_agent.id: custom_agent},
    )

    with patch(
        "app.supervisor.orchestrator._run_custom_agent",
        return_value=AgentRunResult(
            agent_id=custom_agent.id,
            content="ran dataset tool",
            tool_outputs=(
                {
                    "tool_name": "query_dataset_students",
                    "arguments": {"limit": 50},
                    "output": {
                        "row_count": 1,
                        "rows": [{"student_name": "Olivia Rahman", "gpa": 9.3}],
                    },
                },
            ),
        ),
    ):
        response = ProviderSupervisor(provider).run(request)

    assert len(provider.generate_calls) == 2
    assert "final answer" in provider.generate_calls[1][0].content.casefold()
    assert "Who has the highest GPA?" in provider.generate_calls[1][1].content
    assert "Olivia Rahman" in provider.generate_calls[1][1].content
    assert "Readable evidence:" in provider.generate_calls[1][1].content
    assert response.content == "Olivia Rahman has the highest GPA at 9.3."


def test_evidence_refusal_falls_back_to_deterministic_summary() -> None:
    from app.supervisor import _synthesize_final_answer

    class RefusalProvider:
        def generate(self, messages, *, tools=()):
            return ModelResponse(
                content=(
                    "The question is incomplete as it does not provide the full JSON data."
                )
            )

        def stream(self, messages, *, tools=()):
            return iter(())

    result = AgentRunResult(
        agent_id="custom_student",
        content="ignored",
        tool_outputs=(
            {
                "tool_name": "query_dataset_students",
                "arguments": {"limit": 50},
                "output": {
                    "row_count": 2,
                    "rows": [
                        {"student_name": "Ava Chen", "gpa": 9.1},
                        {"student_name": "Olivia Rahman", "gpa": 9.3},
                    ],
                },
            },
        ),
    )
    request = SupervisorRequest(
        selected_agent_ids=("custom_student",),
        messages=(),
        user_input="Who has the highest GPA?",
        agent_catalog={},
    )

    content = _synthesize_final_answer(RefusalProvider(), request, [result])

    assert "full JSON" not in content
    assert "Highest gpa among returned rows: 9.3 (Olivia Rahman)." in content
