from __future__ import annotations

from typing import TYPE_CHECKING

from app.providers.base import ModelMessage
from app.providers.factory import create_model_provider


if TYPE_CHECKING:
    from app.settings import Settings

from app.settings import UI_MODEL_PROVIDERS


def provider_health(settings: Settings, *, live: bool = False) -> list[dict[str, object]]:
    providers = [
        {
            "id": "openai",
            "name": "OpenAI",
            "ready": settings.openai_api_key is not None,
            "missing": [] if settings.openai_api_key else ["OPENAI_API_KEY"],
            "message": (
                "OpenAI is configured."
                if settings.openai_api_key
                else "OPENAI_API_KEY is required."
            ),
        },
        {
            "id": "ollama",
            "name": "Ollama",
            "ready": settings.ollama_model is not None,
            "missing": [] if settings.ollama_model else ["OLLAMA_MODEL"],
            "message": (
                "Ollama is configured."
                if settings.ollama_model
                else "OLLAMA_MODEL is required."
            ),
        },
        {
            "id": "bedrock",
            "name": "Bedrock",
            "ready": settings.bedrock_model_id is not None,
            "missing": [] if settings.bedrock_model_id else ["BEDROCK_MODEL_ID"],
            "message": (
                "Bedrock is configured."
                if settings.bedrock_model_id
                else "BEDROCK_MODEL_ID is required."
            ),
        },
    ]

    ui_providers = [provider for provider in providers if provider["id"] in UI_MODEL_PROVIDERS]

    if not live:
        return ui_providers

    for provider in ui_providers:
        if provider["id"] != settings.model_provider:
            continue
        if not provider["ready"]:
            provider["live_checked"] = False
            provider["live_ready"] = None
            provider["live_message"] = "Live check skipped because provider is not configured."
            break

        try:
            live_message = check_active_provider_live(settings)
        except Exception as error:
            provider["live_checked"] = True
            provider["live_ready"] = False
            provider["live_message"] = str(error)
        else:
            provider["live_checked"] = True
            provider["live_ready"] = True
            provider["live_message"] = live_message
        break

    return ui_providers


def check_active_provider_live(settings: Settings) -> str:
    """Send one tiny request to the active provider."""

    provider = create_model_provider(settings)
    response = provider.generate(
        [ModelMessage(role="user", content="Reply with ok.")],
    )
    if response.content.strip() == "":
        raise ValueError("Provider returned an empty response.")
    return "Live provider check succeeded."
