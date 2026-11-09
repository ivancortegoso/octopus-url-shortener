"""Request logging and correlation.

Enough to answer the three questions an operator asks without reading code: is it up, how
long are requests taking, and what happened to this particular one. Structured records go
to standard output, which is where a container platform collects them from.
"""

import json
import logging
import sys
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import Request, Response

LOGGER_NAME = "shortener.access"
REQUEST_ID_HEADER = "X-Request-ID"

logger = logging.getLogger(LOGGER_NAME)


def record_context(record: logging.LogRecord) -> dict[str, Any]:
    """Return the structured fields attached to a record through `extra`.

    Logging stores anything passed as `extra` in the record's attribute dictionary, which
    is where both the formatter and the tests read it from.
    """
    context: dict[str, Any] = record.__dict__.get("context", {})
    return context


class JsonFormatter(logging.Formatter):
    """Render each record as one JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "event": record.getMessage(),
        }
        payload.update(record_context(record))
        return json.dumps(payload, separators=(",", ":"))


def configure_logging(level: int = logging.INFO) -> None:
    """Send access records to standard output as JSON, once."""
    if logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.setLevel(level)
    # Access records are emitted deliberately; letting them reach the root logger as well
    # would duplicate every line under uvicorn's own configuration.
    logger.propagate = False


async def log_request(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Attach a correlation id to the request, time it, and record the outcome.

    An inbound X-Request-ID is reused so a trace started by a proxy or a caller carries
    through; otherwise one is minted. It goes back on the response so whoever saw the
    failure can quote it.
    """
    request_id = request.headers.get(REQUEST_ID_HEADER) or uuid.uuid4().hex
    started = time.perf_counter()

    response = await call_next(request)

    response.headers[REQUEST_ID_HEADER] = request_id
    logger.info(
        "request",
        extra={
            "context": {
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status": response.status_code,
                "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            }
        },
    )
    return response
