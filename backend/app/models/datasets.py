"""Imported dataset API models."""

from typing import Literal

from pydantic import BaseModel, Field


ColumnType = Literal["string", "number"]


class DatasetColumnResponse(BaseModel):
    name: str
    column_type: ColumnType


class ImportedDatasetResponse(BaseModel):
    id: str
    name: str
    description: str
    original_filename: str
    columns: list[DatasetColumnResponse]
    tool_name: str
    created_at: str
    updated_at: str


class ImportedDatasetsResponse(BaseModel):
    datasets: list[ImportedDatasetResponse]
