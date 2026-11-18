"""FastAPI entry point.

The API is thin: it authenticates, validates request shapes and calls backend
services. Business state changes live in ``backend/``.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from apps.api.routes import (
    actions,
    approvals,
    audit,
    cases,
    evidence,
    identity,
    invoices,
    operations,
    policies,
    reconciliation,
)
from backend import bootstrap
from backend.adapters.oidc.verifier import OidcVerifier
from backend.config import Settings, get_settings
from backend.errors import DomainError
from backend.persistence.database import Database
from backend.runtime import build_runtime
from backend.telemetry.tracing import (
    configure_logging,
    current_trace_id,
    new_trace_id,
    reset_trace_id,
    set_trace_id,
)
from backend.worker import run_once

log = logging.getLogger("finguard.api")

API_VERSION = "v1"


ROUTERS = (
    identity.router,
    evidence.router,
    cases.router,
    policies.router,
    invoices.router,
    actions.router,
    approvals.router,
    reconciliation.router,
    audit.router,
    operations.router,
)


def create_app(settings: Settings | None = None, db: Database | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()
    bootstrap.load()

    app = FastAPI(
        title="FinGuard API",
        version="0.1.0",
        description="Evidence and control platform for AI-assisted financial work.",
    )
    app.state.settings = settings
    app.state.runtime = build_runtime(settings, db)
    app.state.db = app.state.runtime.db
    if settings.oidc_issuer and settings.oidc_audience:
        app.state.oidc_verifier = OidcVerifier(settings.oidc_issuer, settings.oidc_audience)

    app.add_middleware(
        CORSMiddleware,
        # One origin, or several separated by commas (one app served on several domains).
        allow_origins=[o.strip() for o in settings.web_origin.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    if settings.inline_jobs:
        # No separate worker on this host: after each API call, process whatever
        # that call (or an earlier one) queued, before answering. The client
        # refetches after mutations, so it sees the result on its next read.
        runtime = app.state.runtime

        def drain() -> None:
            try:
                run_once(runtime, max_jobs=settings.inline_jobs_max)
            except Exception:  # never fail the request because of queued work
                log.exception("inline job processing failed")

        @app.middleware("http")
        async def inline_jobs_middleware(request: Request, call_next):
            response = await call_next(request)
            if request.method != "OPTIONS" and request.url.path.startswith(f"/{API_VERSION}/"):
                await run_in_threadpool(drain)
            return response

    @app.middleware("http")
    async def trace_middleware(request: Request, call_next):
        token = set_trace_id(new_trace_id(request.headers.get("x-trace-id")))
        try:
            response = await call_next(request)
            response.headers["X-Trace-Id"] = current_trace_id() or ""
            return response
        finally:
            reset_trace_id(token)

    @app.exception_handler(DomainError)
    async def domain_error_handler(_: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "trace_id": current_trace_id(),
                }
            },
        )

    @app.get("/healthz", tags=["meta"])
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get(f"/{API_VERSION}/meta", tags=["meta"])
    def meta() -> dict[str, object]:
        return {
            "name": "FinGuard",
            "api_version": API_VERSION,
            "environment": settings.env,
            "simulation_only": True,
        }

    for router in ROUTERS:
        app.include_router(router)

    return app


app = create_app()
