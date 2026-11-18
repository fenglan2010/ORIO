"""OIRO FastAPI application."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import campaigns, alerts, audit, auth, channels, chat, dashboard, diagnosis, evolution, jobs, memories, ops, reviews, settings, strategies, users, writes
from app.config import validate_runtime_settings
from app.database import init_db, is_postgres_url
from app.schemas import HealthResponse
from app.seed import ensure_seeded
from app.jobs.runtime import job_queue_mode
from app.services.workflow import engine_info

log = logging.getLogger("oiro")

app = FastAPI(title="OIRO", description="OTA 智能收益优化官", version=__version__)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(dashboard.router)
app.include_router(alerts.router)
app.include_router(diagnosis.router)
app.include_router(strategies.router)
app.include_router(campaigns.router)
app.include_router(reviews.router)
app.include_router(chat.router)
app.include_router(audit.router)
app.include_router(settings.router)
app.include_router(channels.router)
app.include_router(ops.router)
app.include_router(writes.router)
app.include_router(jobs.router)
app.include_router(memories.router)
app.include_router(evolution.router)


@app.on_event("startup")
def _startup() -> None:
    settings = validate_runtime_settings()
    backend = "postgresql" if is_postgres_url(settings.database_url) else "sqlite"
    log.info(
        "OIRO starting env=%s database=%s (connection strings are not logged)",
        (settings.oiro_env or "development").strip() or "development",
        backend,
    )
    init_db()
    ensure_seeded()
    engine_info()  # initialize LangGraph if present


@app.get("/api/health", response_model=HealthResponse)
def health():
    info = engine_info()
    return HealthResponse(
        status="ok",
        app="OIRO",
        workflow_engine=info["engine"],
        time=datetime.now(timezone.utc),
        job_queue=job_queue_mode(),
    )
