from dataclasses import FrozenInstanceError

import pytest

from tools import (
    BUILD_CHART_SPEC_TOOL,
    SUMMARIZE_FINDINGS_TOOL,
    LocalTool,
    get_tool,
    list_tool_specs,
    list_tools,
    run_build_chart_spec,
    run_summarize_findings,
    run_tool,
    tool_to_spec,
)


def test_local_tool_captures_metadata_schema_and_runner():
    calls = []

    def run(arguments):
        calls.append(arguments)
        return {"result": arguments["left"] + arguments["right"]}

    tool = LocalTool(
        name="calculator",
        description="Adds two numbers.",
        parameter_schema={
            "type": "object",
            "properties": {
                "left": {"type": "number"},
                "right": {"type": "number"},
            },
            "required": ["left", "right"],
        },
        run=run,
    )

    assert tool.name == "calculator"
    assert tool.description == "Adds two numbers."
    assert tool.parameter_schema["required"] == ["left", "right"]
    assert tool.run({"left": 2, "right": 3}) == {"result": 5}
    assert calls == [{"left": 2, "right": 3}]


def test_local_tool_is_immutable():
    tool = LocalTool(
        name="noop",
        description="Returns nothing.",
        parameter_schema={"type": "object", "properties": {}},
        run=lambda arguments: {},
    )

    with pytest.raises(FrozenInstanceError):
        tool.name = "changed"


def test_tool_to_spec_returns_model_visible_schema():
    tool = LocalTool(
        name="calculator",
        description="Adds two numbers.",
        parameter_schema={
            "type": "object",
            "properties": {
                "left": {"type": "number"},
                "right": {"type": "number"},
            },
        },
        run=lambda arguments: {"result": 0},
    )

    assert tool_to_spec(tool) == {
        "name": "calculator",
        "description": "Adds two numbers.",
        "parameters": {
            "type": "object",
            "properties": {
                "left": {"type": "number"},
                "right": {"type": "number"},
            },
        },
    }


def test_list_tools_returns_registered_tools_in_stable_order():
    assert [tool.name for tool in list_tools()] == [
        "summarize_findings",
        "build_chart_spec",
    ]


def test_get_tool_returns_registered_tool_by_name():
    assert get_tool("summarize_findings") is SUMMARIZE_FINDINGS_TOOL
    assert get_tool("missing") is None


def test_list_tool_specs_returns_all_specs_by_default():
    assert list_tool_specs() == [tool_to_spec(tool) for tool in list_tools()]


def test_list_tool_specs_can_select_tools_by_name():
    assert list_tool_specs(["summarize_findings"]) == [
        tool_to_spec(SUMMARIZE_FINDINGS_TOOL)
    ]


def test_list_tool_specs_rejects_unknown_tool_name():
    with pytest.raises(ValueError, match="Unknown tool: missing"):
        list_tool_specs(["missing"])


def test_run_tool_executes_registered_tool_by_name():
    result = run_tool(
        "summarize_findings",
        {
            "findings": {"row_count": 2, "total_revenue": 100.0},
        },
    )

    assert result["bullets"] == ["Matched 2 rows with $100.00 in revenue."]


def test_run_tool_rejects_unknown_tool_name():
    with pytest.raises(ValueError, match="Unknown tool: missing"):
        run_tool("missing", {})


def test_summarize_findings_converts_structured_findings_to_bullets():
    result = run_summarize_findings(
        {
            "findings": {
                "row_count": 10,
                "total_revenue": 70875.0,
                "total_units": 89,
                "average_margin_pct": 0.507,
                "groups": [
                    {
                        "region": "South",
                        "total_revenue": 20400.0,
                    }
                ],
            }
        }
    )

    assert result == {
        "bullets": [
            "Matched 10 rows with $70,875.00 in revenue.",
            "Total units sold were 89.",
            "Average margin was 50.7%.",
            "Top segment was region South at $20,400.00.",
        ],
        "source_row_count": 10,
    }


def test_summarize_findings_respects_max_bullets():
    result = run_summarize_findings(
        {
            "findings": {
                "row_count": 2,
                "total_revenue": 7560.0,
                "total_units": 42,
                "average_margin_pct": 0.53,
            },
            "max_bullets": 2,
        }
    )

    assert result["bullets"] == [
        "Matched 2 rows with $7,560.00 in revenue.",
        "Total units sold were 42.",
    ]


def test_summarize_findings_handles_empty_findings():
    assert run_summarize_findings({"findings": {}}) == {
        "bullets": ["No summary metrics were available in the supplied findings."],
        "source_row_count": None,
    }


def test_summarize_findings_tool_exposes_schema_and_runner():
    assert SUMMARIZE_FINDINGS_TOOL.name == "summarize_findings"
    assert SUMMARIZE_FINDINGS_TOOL.parameter_schema["required"] == ["findings"]
    assert "max_bullets" in SUMMARIZE_FINDINGS_TOOL.parameter_schema["properties"]
    assert SUMMARIZE_FINDINGS_TOOL.run({"findings": {"row_count": 1}}) == {
        "bullets": ["Matched 1 rows."],
        "source_row_count": 1,
    }


def test_summarize_findings_rejects_invalid_arguments():
    with pytest.raises(ValueError, match="findings must be an object"):
        run_summarize_findings({"findings": "total revenue is high"})

    with pytest.raises(ValueError, match="max_bullets must be between 1 and 8"):
        run_summarize_findings({"findings": {}, "max_bullets": 0})

    with pytest.raises(ValueError, match="max_bullets must be an integer"):
        run_summarize_findings({"findings": {}, "max_bullets": "2"})


def test_build_chart_spec_builds_series_from_grouped_data():
    chart = run_build_chart_spec(
        {
            "title": "Revenue by region",
            "chart_type": "bar",
            "data": [
                {"region": "South", "total_revenue": 20400.0},
                {"region": "Central", "total_revenue": 19750.0},
            ],
            "x_field": "region",
            "y_field": "total_revenue",
        }
    )

    assert chart == {
        "chart_type": "bar",
        "title": "Revenue by region",
        "x_field": "region",
        "y_field": "total_revenue",
        "series": [
            {"label": "South", "value": 20400.0},
            {"label": "Central", "value": 19750.0},
        ],
    }


def test_build_chart_spec_defaults_to_bar_chart_and_generated_title():
    chart = run_build_chart_spec(
        {
            "data": [
                {"order_month": "2026-01", "total_revenue": 19070.0},
                {"order_month": "2026-02", "total_revenue": 21675.0},
            ],
            "x_field": "order_month",
            "y_field": "total_revenue",
        }
    )

    assert chart == {
        "chart_type": "bar",
        "title": "Total Revenue by Order Month (bar)",
        "x_field": "order_month",
        "y_field": "total_revenue",
        "series": [
            {"label": "2026-01", "value": 19070.0},
            {"label": "2026-02", "value": 21675.0},
        ],
    }


def test_build_chart_spec_tool_exposes_schema_and_runner():
    assert BUILD_CHART_SPEC_TOOL.name == "build_chart_spec"
    assert BUILD_CHART_SPEC_TOOL.parameter_schema["required"] == [
        "data",
        "x_field",
        "y_field",
    ]
    assert BUILD_CHART_SPEC_TOOL.parameter_schema["properties"]["chart_type"]["enum"] == [
        "bar",
        "line",
    ]
    assert BUILD_CHART_SPEC_TOOL.run(
        {
            "chart_type": "line",
            "data": [{"month": "2026-01", "revenue": 100.0}],
            "x_field": "month",
            "y_field": "revenue",
        }
    )["chart_type"] == "line"


def test_build_chart_spec_rejects_invalid_arguments():
    with pytest.raises(ValueError, match="data must be a non-empty list"):
        run_build_chart_spec({"data": [], "x_field": "region", "y_field": "revenue"})

    with pytest.raises(ValueError, match="x_field 'region' is missing"):
        run_build_chart_spec(
            {
                "data": [{"channel": "Online", "revenue": 100}],
                "x_field": "region",
                "y_field": "revenue",
            }
        )

    with pytest.raises(ValueError, match="y_field 'revenue' must contain numeric"):
        run_build_chart_spec(
            {
                "data": [{"region": "West", "revenue": "100"}],
                "x_field": "region",
                "y_field": "revenue",
            }
        )

    with pytest.raises(ValueError, match="chart_type must be one of"):
        run_build_chart_spec(
            {
                "chart_type": "pie",
                "data": [{"region": "West", "revenue": 100}],
                "x_field": "region",
                "y_field": "revenue",
            }
        )
