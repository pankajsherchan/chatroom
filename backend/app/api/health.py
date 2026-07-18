"""Health API routes."""

from typing import Annotated

from fastapi import APIRouter, Depends

from app.settings import Settings, get_active_model_provider, get_settings


router = APIRouter()


@router.get("/health")
def health(settings: Annotated[Settings, Depends(get_settings)]):
    return {
        "status": "healthy",
        "model_provider": get_active_model_provider(settings),
    }
