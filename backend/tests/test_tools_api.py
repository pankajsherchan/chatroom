from fastapi.testclient import TestClient

from app.main import app


def test_tools_endpoint_returns_ui_visible_tools_with_schemas_and_examples():
    response = TestClient(app).get("/tools")

    assert response.status_code == 200
    payload = response.json()

    tool_names = [tool["name"] for tool in payload["tools"]]
    assert tool_names[0] == "query_snowflake"
    assert "lookup_account" in tool_names
    assert "summarize_findings" not in tool_names
    assert "build_chart_spec" not in tool_names
    assert "calculator" not in tool_names
    assert "query_sample_sales" not in tool_names

    lookup_account = next(
        tool for tool in payload["tools"] if tool["name"] == "lookup_account"
    )
    assert lookup_account["parameter_schema"]["properties"]["account_id"]["type"] == "string"
    assert lookup_account["examples"][0]["arguments"]["account_id"] == "AC-1001"
