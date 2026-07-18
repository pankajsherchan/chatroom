"""Structured logging and request timing for local debugging."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Iterator
from typing import Any
from uuid import uuid4

logger = logging.getLogger("chatroom")


def new_request_id() -> str:
    return str(uuid4())


def log_event(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, sort_keys=True, default=str))


def duration_ms(started_at: float) -> int:
    return round((time.perf_counter() - started_at) * 1000)


def stream_with_request_logging(
    chunks: Iterator[str],
    *,
    request_id: str,
    conversation_id: str,
    execution_mode: str,
    provider_id: str | None = None,
    model_name: str | None = None,
    selected_agent_ids: list[str] | None = None,
) -> Iterator[str]:
    started_at = time.perf_counter()
    log_event(
        "chat_request_started",
        request_id=request_id,
        conversation_id=conversation_id,
        execution_mode=execution_mode,
        provider_id=provider_id,
        model_name=model_name,
        selected_agent_ids=selected_agent_ids or [],
    )

    status = "success"
    error: str | None = None
    try:
        for chunk in chunks:
            yield chunk
    except Exception as exc:
        status = "error"
        error = str(exc)
        raise
    finally:
        fields: dict[str, Any] = {
            "request_id": request_id,
            "conversation_id": conversation_id,
            "execution_mode": execution_mode,
            "provider_id": provider_id,
            "model_name": model_name,
            "selected_agent_ids": selected_agent_ids or [],
            "status": status,
            "duration_ms": duration_ms(started_at),
        }
        if error is not None:
            fields["error"] = error
        log_event("chat_request_finished", **fields)
