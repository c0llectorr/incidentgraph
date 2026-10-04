"""Application factory: middleware, error envelope, router wiring (PRD §8.5/8.6).

Error handlers guarantee the stable envelope and guarantee that stack traces,
environment variables, provider credentials, internal paths, and raw provider
responses never reach the client.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response

from app.api import dependencies
from app.api.dependencies import AppContainer
from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.errors import IncidentGraphError
from app.core.ids import new_request_id
from app.core.logging import configure_logging, get_logger, get_request_id, set_request_id
from app.persistence.models import Base
from app.schemas.common import ErrorEnvelope

logger = get_logger(__name__)


def _envelope_response(
    *, status: int, code: str, message: str, retryable: bool
) -> JSONResponse:
    body = ErrorEnvelope(
        error={
            "code": code,
            "message": message,
            "request_id": get_request_id() or "-",
            "retryable": retryable,
        }
    )
    return JSONResponse(status_code=status, content=body.model_dump())


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    container: AppContainer = app.state.container
    # Idempotent dev convenience: create the schema when it does not exist so
    # a fresh checkout boots without a migration step. Alembic remains the
    # canonical tool for real migrations; create_all is a no-op afterwards.
    assert container.engine is not None
    Base.metadata.create_all(bind=container.engine)
    logger.info("IncidentGraph API starting (env=%s)", container.settings.app_env)
    yield
    logger.info("IncidentGraph API stopped")


def create_app(
    settings: Settings | None = None,
    container: AppContainer | None = None,
) -> FastAPI:
    resolved_settings = settings or get_settings()
    resolved_container = container or dependencies.build_container(resolved_settings)
    resolved_container.settings = resolved_settings
    dependencies.init_container(resolved_container)
    configure_logging()

    app = FastAPI(
        title="IncidentGraph API",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.container = resolved_container

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[resolved_settings.frontend_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next: Callable[[Request], Response]) -> Response:
        incoming = request.headers.get("X-Request-ID") or new_request_id()
        set_request_id(incoming)
        response = await call_next(request)
        response.headers["X-Request-ID"] = incoming
        return response

    @app.exception_handler(IncidentGraphError)
    async def incidentgraph_error_handler(_: Request, exc: IncidentGraphError) -> JSONResponse:
        logger.warning("Handled error code=%s: %s", exc.code, exc.message)
        return _envelope_response(
            status=exc.http_status,
            code=exc.code,
            message=exc.message,
            retryable=exc.retryable,
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        # Full diagnostics belong in protected server logs only (PRD §8.6).
        logger.exception("Unhandled error: %s", type(exc).__name__)
        return _envelope_response(
            status=500,
            code="INTERNAL_ERROR",
            message="An internal error occurred.",
            retryable=False,
        )

    app.include_router(api_router, prefix=resolved_settings.api_v1_prefix)
    return app


# Deployment entry point: `uvicorn app.main:app` binds this instance.
# Tests and alternative compositions build their own app via create_app().
app = create_app()
