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
from app.events.logging_subscriber import register_logging_subscriber
from app.events.registry import get_event_bus
from app.websocket.manager import ConnectionManager
from app.websocket.playback_routes import router as playback_websocket_router
from app.websocket.routes import router as websocket_router

logger = logging.getLogger(__name__)


def ensure_simulation_only(settings: Settings) -> None:
    if not settings.simulation_only:
        raise ConfigurationError(
            "AegisArena cannot start with SIMULATION_ONLY=false. Real-world mode is prohibited."
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
        try:
            active_settings.model_artifact_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            database.dispose()
            raise ConfigurationError(
                "Model artifact directory is unavailable during startup"
            ) from exc
        if not active_settings.model_artifact_dir.is_dir():
            database.dispose()
            raise ConfigurationError("MODEL_ARTIFACT_DIR must identify a directory")
        logger.info("Model artifact directory verified")
        event_bus = get_event_bus()
        register_logging_subscriber(event_bus)
        application.state.event_bus = event_bus
        logger.info("Event bus initialised (InProcessEventBus)")
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
    application.include_router(playback_websocket_router)
    register_exception_handlers(application)
    return application


app = create_app()
