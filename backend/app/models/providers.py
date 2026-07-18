"""Provider API models."""

from pydantic import BaseModel


class ProviderHealthResponse(BaseModel):
    id: str
    name: str
    ready: bool
    missing: list[str]
    message: str
    live_checked: bool = False
    live_ready: bool | None = None
    live_message: str | None = None


class ProvidersHealthResponse(BaseModel):
    active_provider: str
    providers: list[ProviderHealthResponse]


class SetActiveProviderRequest(BaseModel):
    provider_id: str


class SetActiveProviderResponse(BaseModel):
    active_provider: str
