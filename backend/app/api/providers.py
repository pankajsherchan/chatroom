"""Provider readiness API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.models import (
    ProvidersHealthResponse,
    SetActiveProviderRequest,
    SetActiveProviderResponse,
)
from app.providers import provider_health
from app.settings import (
    Settings,
    effective_settings,
    get_active_model_provider,
    get_settings,
    set_active_model_provider,
)


router = APIRouter()


def _providers_payload(settings: Settings, *, live: bool = False) -> dict[str, object]:
    runtime_settings = effective_settings(settings)
    return {
        "active_provider": get_active_model_provider(settings),
        "providers": provider_health(runtime_settings, live=live),
    }


@router.get("/providers", response_model=ProvidersHealthResponse)
def providers(settings: Annotated[Settings, Depends(get_settings)]):
    return _providers_payload(settings)


@router.get("/providers/health", response_model=ProvidersHealthResponse)
def providers_health(
    settings: Annotated[Settings, Depends(get_settings)],
    live: Annotated[bool, Query()] = False,
):
    return _providers_payload(settings, live=live)


@router.put("/providers/active", response_model=SetActiveProviderResponse)
def set_active_provider(
    request: SetActiveProviderRequest,
    settings: Annotated[Settings, Depends(get_settings)],
):
    try:
        active_provider = set_active_model_provider(request.provider_id)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {"active_provider": active_provider}
