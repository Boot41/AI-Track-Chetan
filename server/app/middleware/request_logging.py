from __future__ import annotations

from uuid import uuid4
import time

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id
        start = time.perf_counter()
        response = await call_next(request)
        duration_ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = request_id

        logger.info(
            "{method} {path} {status} {duration:.1f}ms client={client} request_id={request_id}",
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            duration=duration_ms,
            client=request.client.host if request.client else "-",
            request_id=request_id,
        )
        return response
