"""RequestId middleware: injects X-Request-Id into every request context.

- Reads X-Request-Id header from the incoming request.
- Falls back to a generated UUID4 if the header is absent.
- Stores the id in the request_id_ctx ContextVar (used by ops.logging).
- Echoes the id back in the X-Request-Id response header.

Registration (main.py):
    from ops.middleware import RequestIdMiddleware
    app.add_middleware(RequestIdMiddleware)
"""
from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from ops.logging import request_id_ctx


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
