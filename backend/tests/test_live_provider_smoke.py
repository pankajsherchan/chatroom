"""Opt-in smoke tests for real model providers.

These tests intentionally skip by default. Enable them only when you want to
spend real provider calls or hit a local Ollama service:

    RUN_LIVE_PROVIDER_SMOKE=1 MODEL_PROVIDER=openai OPENAI_API_KEY=... uv run pytest tests/test_live_provider_smoke.py
"""

import os

import pytest

from app.providers import ModelMessage, create_model_provider
from app.settings import Settings


LIVE_SMOKE_ENV = "RUN_LIVE_PROVIDER_SMOKE"


@pytest.mark.parametrize(
    ("provider_id", "required_env"),
    [
        ("openai", ("OPENAI_API_KEY",)),
        ("ollama", ("OLLAMA_MODEL",)),
        ("bedrock", ("BEDROCK_MODEL_ID",)),
    ],
)
def test_live_provider_generate_returns_non_empty_text(
    provider_id: str,
    required_env: tuple[str, ...],
):
    if os.environ.get(LIVE_SMOKE_ENV) != "1":
        pytest.skip(f"Set {LIVE_SMOKE_ENV}=1 to run live provider smoke tests.")

    missing = [key for key in required_env if not os.environ.get(key)]
    if missing:
        pytest.skip(
            f"{provider_id} live smoke skipped; missing {', '.join(missing)}."
        )

    env = dict(os.environ)
    env["MODEL_PROVIDER"] = provider_id
    settings = Settings.from_env(env)
    provider = create_model_provider(settings)

    response = provider.generate(
        [
            ModelMessage(
                role="user",
                content="Reply with one short sentence confirming the provider works.",
            )
        ]
    )

    assert response.content.strip()
