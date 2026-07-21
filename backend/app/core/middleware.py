from __future__ import annotations

import logging
import re
import time
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.constants import CORRELATION_HEADER, MAX_CORRELATION_ID_LENGTH
from app.core.logging import reset_correlation_id, set_correlation_id

logger = logging.getLogger(__name__)
VALID_CORRELATION_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


def normalise_correlation_id(value: str | None) -> str:
    if value is not None and len(value) <= MAX_CORRELATION_ID_LENGTH:
        candidate = value.strip()
        if VALID_CORRELATION_ID.fullmatch(candidate):
            return candidate
    return str(uuid4())


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        correlation_id = normalise_correlation_id(request.headers.get(CORRELATION_HEADER))
        request.state.correlation_id = correlation_id
        token = set_correlation_id(correlation_id)
        started = time.perf_counter()
        try:
            response = await call_next(request)
            response.headers[CORRELATION_HEADER] = correlation_id
            elapsed_ms = (time.perf_counter() - started) * 1000
            logger.info(
                "HTTP request completed method=%s path=%s status=%d duration_ms=%.2f",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
            return response
        finally:
            reset_correlation_id(token)
