"""RequestId middleware: injects X-Request-Id into every request context.

- Reads X-Request-Id header from the incoming request.
- Falls back to a generated UUID4 if the header is absent.
- Stores the id in the request_id_ctx ContextVar (used by ops.logging).
- Echoes the id back in the X-Request-Id response header.

APILoggingMiddleware: logs every API request/response to MongoDB (application_logs)
with method, path, status_code, duration_ms, request_id.

Registration (main.py):
    from ops.middleware import RequestIdMiddleware, APILoggingMiddleware
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(APILoggingMiddleware)
"""
from __future__ import annotations

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ops.logging import request_id_ctx, get_logger

logger = get_logger(__name__)


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Attach a unique request_id to every HTTP request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        # Prefer header value; otherwise generate a fresh UUID
        request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())

        # Bind to ContextVar so ops.logging can read it in processors
        token = request_id_ctx.set(request_id)
        try:
            response: Response = await call_next(request)
        finally:
            # Always restore the ContextVar even on exceptions
            request_id_ctx.reset(token)

        response.headers["X-Request-Id"] = request_id
        return response


class APILoggingMiddleware(BaseHTTPMiddleware):
    """Log every API request to MongoDB (application_logs) with method, path, status_code, duration_ms."""

    async def dispatch(self, request: Request, call_next) -> Response:
        method = request.method
        path = request.url.path
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        status_code = response.status_code
        logger.info(
            "api_request",
            method=method,
            path=path,
            status_code=status_code,
            duration_ms=duration_ms,
        )
        return response
