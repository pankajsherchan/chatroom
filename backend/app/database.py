"""Database connection helpers for the local backend."""

import sqlite3
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends

from app.settings import Settings, get_settings
from app.storage import connect_database


def get_database_connection(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[sqlite3.Connection]:
    connection = connect_database(settings.sqlite_db_path)
    try:
        yield connection
    finally:
        connection.close()
