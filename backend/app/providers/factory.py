from app.providers.openai import DEFAULT_OPENAI_MODEL, OpenAIProvider
from app.providers.ollama import OllamaProvider
from app.providers.bedrock import BedrockProvider
from app.providers.base import ModelProvider
from app.settings import Settings

__all__ = ["DEFAULT_OPENAI_MODEL", "create_model_provider"]


def create_model_provider(settings: Settings) -> ModelProvider:
    """Create the configured model provider implementation."""

    if settings.model_provider == "openai":
        if settings.openai_api_key is None:
            raise ValueError("OPENAI_API_KEY is required when MODEL_PROVIDER='openai'.")
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.openai_model or DEFAULT_OPENAI_MODEL,
        )

    if settings.model_provider == "ollama":
        if settings.ollama_model is None:
            raise ValueError("OLLAMA_MODEL is required when MODEL_PROVIDER='ollama'.")
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.ollama_model,
        )

    if settings.model_provider == "bedrock":
        if settings.bedrock_model_id is None:
            raise ValueError("BEDROCK_MODEL_ID is required when MODEL_PROVIDER='bedrock'.")
        return BedrockProvider(
            model_id=settings.bedrock_model_id,
            region=settings.aws_region,
            aws_profile=settings.aws_profile,
        )

    raise ValueError(f"Unsupported MODEL_PROVIDER={settings.model_provider!r}.")
