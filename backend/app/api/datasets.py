"""Imported dataset CRUD API routes."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from app.database import get_database_connection
from app.models.datasets import ImportedDatasetResponse, ImportedDatasetsResponse
from app.settings import get_settings
from app.storage import (
    ImportedDatasetRecord,
    DatasetColumnRecord,
    create_imported_dataset,
    delete_imported_dataset,
    get_imported_dataset,
    list_imported_datasets,
)
from tools.csv_schema import inspect_csv_columns


router = APIRouter()

MAX_DATASET_BYTES = 2 * 1024 * 1024


@router.get("/datasets", response_model=ImportedDatasetsResponse)
def datasets_list(
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
):
    return ImportedDatasetsResponse(
        datasets=[_dataset_to_response(dataset) for dataset in list_imported_datasets(connection)]
    )


@router.get("/datasets/{dataset_id}", response_model=ImportedDatasetResponse)
def dataset_detail(
    dataset_id: str,
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
):
    found = get_imported_dataset(connection, dataset_id)
    if found is None:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")
    return _dataset_to_response(found)


@router.post("/datasets", response_model=ImportedDatasetResponse, status_code=201)
async def datasets_create(
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
    file: Annotated[UploadFile, File(...)],
    name: Annotated[str, Form(...)],
    description: Annotated[str, Form()] = "",
):
    cleaned_name = name.strip()
    if cleaned_name == "":
        raise HTTPException(status_code=400, detail="Dataset name is required.")

    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Upload must be a .csv file.")

    payload = await file.read()
    if len(payload) == 0:
        raise HTTPException(status_code=400, detail="CSV file is empty.")
    if len(payload) > MAX_DATASET_BYTES:
        raise HTTPException(status_code=400, detail="CSV file exceeds the 2 MB import limit.")

    settings = get_settings()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as temp_file:
        temp_path = Path(temp_file.name)
        temp_path.write_bytes(payload)

    try:
        columns = inspect_csv_columns(temp_path)
        cleaned_description = description.strip() or f"Imported dataset from {file.filename}."
        created = create_imported_dataset(
            connection,
            name=cleaned_name,
            description=cleaned_description,
            source_csv_path=temp_path,
            original_filename=file.filename,
            datasets_dir=settings.imported_datasets_dir,
            columns=[
                DatasetColumnRecord(name=column.name, column_type=column.column_type)
                for column in columns
            ],
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    finally:
        temp_path.unlink(missing_ok=True)

    return _dataset_to_response(created)


@router.delete("/datasets/{dataset_id}", status_code=204)
def datasets_delete(
    dataset_id: str,
    connection: Annotated[sqlite3.Connection, Depends(get_database_connection)],
):
    deleted = delete_imported_dataset(connection, dataset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Dataset not found: {dataset_id}")


def _dataset_to_response(record: ImportedDatasetRecord) -> ImportedDatasetResponse:
    return ImportedDatasetResponse(
        id=record.id,
        name=record.name,
        description=record.description,
        original_filename=record.original_filename,
        columns=[
            {"name": column.name, "column_type": column.column_type}  # type: ignore[misc]
            for column in record.columns
        ],
        tool_name=record.tool_name,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
