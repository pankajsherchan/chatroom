from app.turn_report import TurnTrace, render_turn_report_html, write_turn_report
from app.settings import get_settings


def test_write_turn_report_creates_html_and_json(tmp_path, monkeypatch):
    monkeypatch.setenv("TURN_REPORTS_ENABLED", "1")
    monkeypatch.setenv("TURN_REPORTS_DIR", str(tmp_path))
    get_settings.cache_clear()

    trace = TurnTrace()
    trace.meta["user_input"] = "show revenue by region"
    trace.add(
        "manager",
        "Manager chose specialists",
        what_this_step_does="Manager routing only.",
        received_from_ui={
            "user_prompt": "show revenue by region",
            "conversation_team_agent_ids": ["supervisor", "connector_sales_pipeline"],
            "prior_messages_in_request": 1,
        },
        available_specialists=[
            {
                "id": "connector_sales_pipeline",
                "name": "Sales pipeline",
                "description": "Query deals",
                "tools": ["query_snowflake"],
            }
        ],
        manager_system_message="You are the local group chat manager.",
        manager_user_message="Choose specialists for: show revenue by region",
        provider_call={
            "method": "provider.generate(messages, tools=())",
            "tools_passed": [],
        },
        raw_provider_content='{"agent_ids": ["connector_sales_pipeline"]}',
        decision={
            "chosen_agent_ids": ["connector_sales_pipeline"],
            "used_keyword_routing_fallback": False,
            "fallback_meaning": "Provider returned usable agent_ids JSON.",
        },
    )
    trace.add(
        "specialist_tool_loop",
        "Specialist asked for tools",
        agent_id="connector_sales_pipeline",
        agent_name="Sales pipeline",
        messages=[
            {"role": "system", "content": "Use query_snowflake"},
            {"role": "user", "content": "show revenue by region"},
        ],
        tool_specs=[{"name": "query_snowflake"}],
        tool_calls=[{"name": "query_snowflake", "arguments": {"sql": "SELECT 1"}}],
    )
    trace.add(
        "tool_execution",
        "Ran query_snowflake",
        tool_name="query_snowflake",
        status="ok",
        arguments={"sql": "SELECT 1", "max_rows": "10"},
        argument_types={"sql": "str", "max_rows": "str"},
        output={"row_count": 1, "rows": [{"region": "West"}]},
    )
    trace.add(
        "final_answer",
        "Final answer synthesis",
        used_model_answer=True,
        final_text="West has revenue.",
        messages=[
            {"role": "system", "content": "Write the final answer"},
            {"role": "user", "content": "User question: show revenue by region"},
        ],
    )

    html_path = write_turn_report(
        trace,
        conversation_id="conv-123",
        request_id="req-456",
        provider_id="ollama",
        model_name="llama3.2",
        final_answer="West has revenue.",
        selected_agent_ids=["supervisor", "connector_sales_pipeline"],
        request_context={
            "ui_action": "User typed a message in the chat composer and pressed send.",
            "http_method": "POST",
            "api_endpoint": "/conversations/conv-123/messages/stream",
            "request_body": {"content": "show revenue by region"},
            "request_id": "req-456",
            "conversation_id": "conv-123",
            "persisted_before_supervisor": {"user_message_appended": True},
            "runtime": {"provider_id": "ollama", "model_name": "llama3.2"},
            "next_step": "Run ProviderSupervisor",
        },
    )

    assert html_path is not None
    assert html_path.exists()
    json_path = html_path.with_suffix(".json")
    assert json_path.exists()

    html = html_path.read_text(encoding="utf-8")
    assert "show revenue by region" in html
    assert "query_snowflake" in html
    assert "manager" in html
    assert "[PASS]" in html
    assert "API endpoint called" in html
    assert "/conversations/conv-123/messages/stream" in html
    assert "From the UI" in html
    assert "What this step is" in html
    assert "Messages sent to the LLM (JSON)" in html
    assert "Raw step JSON" not in html
    # LLM message JSON appears for manager, specialist, and final — not every step.
    assert html.count("Messages sent to the LLM (JSON)") == 3


def test_turn_reports_can_be_disabled(tmp_path, monkeypatch):
    monkeypatch.setenv("TURN_REPORTS_ENABLED", "0")
    monkeypatch.setenv("TURN_REPORTS_DIR", str(tmp_path))
    get_settings.cache_clear()

    path = write_turn_report(
        TurnTrace(),
        conversation_id="conv",
        final_answer="noop",
    )
    assert path is None
    assert list(tmp_path.iterdir()) == []


def test_write_turn_report_redacts_secret_fields(tmp_path, monkeypatch):
    monkeypatch.setenv("TURN_REPORTS_ENABLED", "1")
    monkeypatch.setenv("TURN_REPORTS_DIR", str(tmp_path))
    get_settings.cache_clear()

    trace = TurnTrace()
    trace.meta["user_input"] = "lookup account"
    trace.add(
        "tool_execution",
        "Ran lookup_account",
        arguments={"account_id": "AC-1001", "api_key": "super-secret"},
        snowflake_password="should-not-leak",
    )

    html_path = write_turn_report(
        trace,
        conversation_id="conv-secret",
        final_answer="ok",
    )
    assert html_path is not None
    html = html_path.read_text(encoding="utf-8")
    json_text = html_path.with_suffix(".json").read_text(encoding="utf-8")
    assert "super-secret" not in html
    assert "should-not-leak" not in html
    assert "[REDACTED]" in html
    assert "super-secret" not in json_text
    assert "[REDACTED]" in json_text


def test_render_turn_report_html_escapes_user_content():
    html = render_turn_report_html(
        {
            "meta": {
                "user_input": "<script>alert(1)</script>",
                "final_answer": "ok",
            },
            "steps": [
                {
                    "stage": "manager",
                    "title": "Manager",
                    "data": {"raw": "x"},
                }
            ],
        }
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
