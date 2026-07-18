"""FastAPI application entrypoint for the ChatRoom backend."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.agents import router as agents_router
from app.api.conversations import router as conversations_router
from app.api.health import router as health_router
from app.api.providers import router as providers_router
from app.api.tools import router as tools_router
from app.api.connectors import router as connectors_router
from app.api.custom_agents import router as custom_agents_router
from app.api.datasets import router as datasets_router
from app.artifacts import ARTIFACTS_ROUTE, ensure_artifact_directory
from app.errors import register_error_handlers
from app.settings import get_settings


logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="ChatRoom API",
    version="0.1.0",
    description="Backend API for ChatRoom multi-agent orchestration.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

register_error_handlers(app)
app.include_router(health_router)
app.include_router(agents_router)
app.include_router(providers_router)
app.include_router(connectors_router)
app.include_router(tools_router)
app.include_router(custom_agents_router)
app.include_router(datasets_router)
app.include_router(conversations_router)
app.mount(
    ARTIFACTS_ROUTE,
    StaticFiles(directory=ensure_artifact_directory(get_settings().artifact_static_dir)),
    name="artifacts",
)
