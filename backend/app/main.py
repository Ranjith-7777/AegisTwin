from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import Settings, get_settings
from app.core.constants import APP_DESCRIPTION
from app.core.exceptions import ConfigurationError, register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import CorrelationIdMiddleware
from app.database.session import Database
from app.websocket.manager import ConnectionManager
from app.websocket.routes import router as websocket_router

logger = logging.getLogger(__name__)


def ensure_simulation_only(settings: Settings) -> None:
    if not settings.simulation_only:
        raise ConfigurationError(
            "AegisTwin cannot start with SIMULATION_ONLY=false. Real-world mode is prohibited."
        )


def create_app(settings: Settings | None = None) -> FastAPI:
    active_settings = settings or get_settings()
    configure_logging(active_settings.log_level)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        ensure_simulation_only(active_settings)
        logger.info("Simulation-only enforcement active")
        database = Database(active_settings.database_url)
        application.state.database = database
        if not database.is_connected():
            database.dispose()
            raise ConfigurationError("Database connectivity verification failed during startup")
        logger.info("Database connectivity verified")
        logger.info("Application startup complete")
        try:
            yield
        finally:
            logger.info("Application shutdown started")
            database.dispose()

    application = FastAPI(
        title=active_settings.app_name,
        description=APP_DESCRIPTION,
        version="0.1.0",
        debug=active_settings.debug,
        lifespan=lifespan,
    )
    application.state.settings = active_settings
    application.state.connection_manager = ConnectionManager()
    application.add_middleware(CorrelationIdMiddleware)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=active_settings.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Correlation-ID"],
    )
    application.include_router(api_router, prefix=active_settings.api_prefix)
    application.include_router(websocket_router)
    register_exception_handlers(application)
    return application


app = create_app()
