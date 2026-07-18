from pathlib import Path

from tools.imported_dataset import build_dataset_tool, run_dataset_query
from tools.csv_schema import DatasetColumn


def test_run_dataset_query_filters_and_groups_imported_csv(tmp_path: Path):
    csv_path = tmp_path / "pipeline.csv"
    csv_path.write_text(
        "region,revenue,units\n"
        "West,100,2\n"
        "West,200,3\n"
        "East,50,1\n",
        encoding="utf-8",
    )
    columns = [
        DatasetColumn(name="region", column_type="string"),
        DatasetColumn(name="revenue", column_type="number"),
        DatasetColumn(name="units", column_type="number"),
    ]

    result = run_dataset_query(
        file_path=csv_path,
        columns=columns,
        string_columns=["region"],
        numeric_columns=["revenue", "units"],
        arguments={"filters": {"region": "West"}, "group_by": "region", "limit": 10},
    )

    assert result["row_count"] == 2
    assert result["total_revenue"] == 300.0
    assert result["groups"] == [
        {
            "region": "West",
            "row_count": 2,
            "total_revenue": 300.0,
            "total_units": 5.0,
            "average_revenue": 150.0,
            "average_units": 2.5,
        }
    ]


def test_build_dataset_tool_exposes_dynamic_schema(tmp_path: Path):
    csv_path = tmp_path / "pipeline.csv"
    csv_path.write_text("region,revenue\nWest,100\n", encoding="utf-8")

    tool = build_dataset_tool(
        dataset_id="dataset_test",
        name="Pipeline",
        description="Imported pipeline data.",
        file_path=csv_path,
        columns=[
            DatasetColumn(name="region", column_type="string"),
            DatasetColumn(name="revenue", column_type="number"),
        ],
    )

    assert tool.name == "query_dataset_test"
    assert tool.parameter_schema["properties"]["group_by"]["enum"] == ["region"]
    assert tool.parameter_schema["properties"]["filters"]["properties"] == {
        "region": {"type": "string"}
    }
    assert tool.run({"limit": 5})["row_count"] == 1
