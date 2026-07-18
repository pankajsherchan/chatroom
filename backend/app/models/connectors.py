"""External connector API models."""

from pydantic import BaseModel


class ConnectorHealthResponse(BaseModel):
    id: str
    name: str
    purpose: str
    configuration_hint: str
    tool_name: str
    ready: bool
    missing: list[str]
    message: str


class ConnectorsHealthResponse(BaseModel):
    connectors: list[ConnectorHealthResponse]
