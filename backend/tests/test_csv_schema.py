from pathlib import Path

import pytest

from tools.csv_schema import inspect_csv_columns


def test_inspect_csv_columns_infers_string_and_number_types(tmp_path: Path):
    csv_path = tmp_path / "pipeline.csv"
    csv_path.write_text(
        "region,revenue,units\n"
        "West,1200.5,4\n"
        "East,900,3\n",
        encoding="utf-8",
    )

    columns = inspect_csv_columns(csv_path)

    assert [(column.name, column.column_type) for column in columns] == [
        ("region", "string"),
        ("revenue", "number"),
        ("units", "number"),
    ]


def test_inspect_csv_columns_rejects_missing_data_rows(tmp_path: Path):
    csv_path = tmp_path / "empty.csv"
    csv_path.write_text("region,revenue\n", encoding="utf-8")

    with pytest.raises(ValueError, match="at least one data row"):
        inspect_csv_columns(csv_path)


def test_inspect_csv_columns_rejects_duplicate_headers(tmp_path: Path):
    csv_path = tmp_path / "duplicate.csv"
    csv_path.write_text("region,region\nWest,1\n", encoding="utf-8")

    with pytest.raises(ValueError, match="unique"):
        inspect_csv_columns(csv_path)
