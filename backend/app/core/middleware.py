"""Request correlation and latency measurement middleware."""

import time
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("algotrade")


class RequestCorrelationMiddleware(BaseHTTPMiddleware):
    """Generates or propagates X-Request-ID and tracks request latency."""

    async def dispatch(self, request: Request, call_next) -> Response:
        req_id = request.headers.get("X-Request-ID") or f"req_{uuid.uuid4().hex[:12]}"
        request.state.request_id = req_id

        start_time = time.perf_counter()
        try:
            response: Response = await call_next(request)
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            response.headers["X-Request-ID"] = req_id
            response.headers["X-Response-Time-MS"] = str(duration_ms)

            logger.info(
                f"{request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)",
                extra={"request_id": req_id, "component": "http", "event": "request_completed"},
            )
            return response
        except Exception as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception(
                f"Unhandled error in {request.method} {request.url.path} ({duration_ms}ms): {e}",
                extra={"request_id": req_id, "component": "http", "event": "request_failed"},
            )
            raise
