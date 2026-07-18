"""Optional external connector readiness API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.connectors.external_api import external_api_connector_health
from app.connectors.snowflake import snowflake_connector_health
from app.models.connectors import ConnectorsHealthResponse
from app.settings import Settings, get_settings


router = APIRouter()


@router.get("/connectors", response_model=ConnectorsHealthResponse)
def connectors(settings: Annotated[Settings, Depends(get_settings)]):
    return ConnectorsHealthResponse(
        connectors=[
            snowflake_connector_health(settings),
            external_api_connector_health(settings),
        ],
    )
