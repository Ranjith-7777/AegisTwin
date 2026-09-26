from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from app.schemas.common import ApiError

logger = logging.getLogger(__name__)


class ConfigurationError(RuntimeError):
    """Raised when configuration violates a mandatory project boundary."""


class ApplicationError(Exception):
    def __init__(self, error_code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code


def _correlation_id(request: Request) -> str:
    return str(getattr(request.state, "correlation_id", "unavailable"))


def _response(request: Request, status_code: int, error_code: str, message: str) -> JSONResponse:
    body = ApiError(
        error_code=error_code,
        message=message,
        correlation_id=_correlation_id(request),
    )
    return JSONResponse(status_code=status_code, content=body.model_dump())


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApplicationError)
    async def application_error_handler(request: Request, exc: ApplicationError) -> JSONResponse:
        logger.warning("Handled application error: %s", exc.error_code)
        return _response(request, exc.status_code, exc.error_code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning("Request validation failed with %d error(s)", len(exc.errors()))
        return _response(request, 422, "VALIDATION_ERROR", "The request is invalid.")

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        code = "NOT_FOUND" if exc.status_code == 404 else "HTTP_ERROR"
        message = (
            "The requested resource was not found." if exc.status_code == 404 else str(exc.detail)
        )
        return _response(request, exc.status_code, code, message)

    @app.exception_handler(Exception)
    async def unknown_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled server error", exc_info=exc)
        return _response(
            request, 500, "INTERNAL_SERVER_ERROR", "An unexpected server error occurred."
        )
