from pathlib import Path

from app.storage import (
    DatasetColumnRecord,
    connect_database,
    create_imported_dataset,
    delete_imported_dataset,
    get_imported_dataset_by_tool_name,
    list_imported_datasets,
)


def test_imported_dataset_storage_round_trip(tmp_path: Path):
    db_path = tmp_path / "chatroom.sqlite3"
    datasets_dir = tmp_path / "datasets"
    source_csv = tmp_path / "pipeline.csv"
    source_csv.write_text(
        "region,revenue\n"
        "West,100\n"
        "East,200\n",
        encoding="utf-8",
    )

    connection = connect_database(db_path)
    try:
        created = create_imported_dataset(
            connection,
            name="Pipeline",
            description="Quarterly pipeline CSV.",
            source_csv_path=source_csv,
            original_filename="pipeline.csv",
            datasets_dir=datasets_dir,
            columns=[
                DatasetColumnRecord(name="region", column_type="string"),
                DatasetColumnRecord(name="revenue", column_type="number"),
            ],
        )
        assert created.tool_name.startswith("query_dataset_")
        assert created.file_path.exists()

        listed = list_imported_datasets(connection)
        assert len(listed) == 1
        assert listed[0].id == created.id

        found = get_imported_dataset_by_tool_name(connection, created.tool_name)
        assert found is not None
        assert found.name == "Pipeline"

        assert delete_imported_dataset(connection, created.id) is True
        assert not created.file_path.exists()
        assert list_imported_datasets(connection) == []
    finally:
        connection.close()
