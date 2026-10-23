"""FastAPI application factory and middleware configuration for BRA API."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import ApiConfig, get_config
from .routers import (
    analysis_runs,
    corporate_actions,
    datasets,
    health,
    lookahead,
    reports,
    schemas,
    survivorship,
    validation,
)
from .storage import StorageManager

logger = logging.getLogger("bra.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize storage resources on startup."""
    config = get_config()
    StorageManager(config)
    yield


def create_app(config: ApiConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""
    cfg = config or get_config()

    app = FastAPI(
        title="Backtest Reliability Analyzer (BRA) API",
        description=(
            "Production-minded REST API for data validation, schema mapping, and bias detection "
            "(survivorship, look-ahead, corporate actions) across historical market datasets."
        ),
        version=cfg.version,
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception Handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request, exc: HTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Request validation failed.",
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        # Never expose local filesystem paths or stack traces in public responses
        logger.error(f"Unhandled server error: {type(exc).__name__}: {exc}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "An internal server error occurred while processing the request."
            },
        )

    # Register Routers
    app.include_router(health.router)
    app.include_router(datasets.router)
    app.include_router(schemas.router)
    app.include_router(validation.router)
    app.include_router(survivorship.router)
    app.include_router(lookahead.router)
    app.include_router(corporate_actions.router)
    app.include_router(analysis_runs.router)
    app.include_router(reports.router)

    return app


app = create_app()
