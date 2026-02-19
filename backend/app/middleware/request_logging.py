import json
import logging
import time
import uuid
from collections.abc import Callable

from fastapi import Request, Response

from app.config.settings import settings

request_logger = logging.getLogger("app.request")

_SENSITIVE_HEADER_KEYS = {
    "authorization",
    "cookie",
    "set-cookie",
    "x-shopify-access-token",
    "x-api-key",
}

# Paths that are too chatty to log at INFO (health checks, etc.)
_LOW_NOISE_PATHS = {"/health"}


def _mask_value(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


def _sanitize_headers(headers: dict[str, str]) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for key, value in headers.items():
        if key.lower() in _SENSITIVE_HEADER_KEYS:
            sanitized[key] = _mask_value(value)
        else:
            sanitized[key] = value
    return sanitized


def _log_as_json(logger: logging.Logger, level: int, data: dict) -> None:
    """Emit *data* as a compact JSON string at the given log *level*."""
    logger.log(level, json.dumps(data, ensure_ascii=True))


async def log_requests_middleware(request: Request, call_next: Callable) -> Response:
    request_id = str(uuid.uuid4())
    started = time.perf_counter()
    path = request.url.path

    # Choose a lower log level for noisy health-check endpoints
    is_low_noise = path in _LOW_NOISE_PATHS
    incoming_level = logging.DEBUG if is_low_noise else logging.INFO

    # Buffer the body so we can log it and still pass it downstream
    request_body = await request.body()
    body_text = request_body.decode("utf-8", errors="replace")
    if len(body_text) > settings.request_log_body_limit:
        body_text = body_text[: settings.request_log_body_limit] + "...<truncated>"

    _log_as_json(
        request_logger,
        incoming_level,
        {
            "event": "request_received",
            "request_id": request_id,
            "method": request.method,
            "path": path,
            "query_params": dict(request.query_params),
            "client": request.client.host if request.client else None,
            "headers": _sanitize_headers(dict(request.headers)),
            "body": body_text,
        },
    )

    # Re-wrap the request so the body is still readable by route handlers
    async def receive() -> dict:
        return {"type": "http.request", "body": request_body, "more_body": False}

    request = Request(request.scope, receive)

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        request_logger.exception(
            json.dumps(
                {
                    "event": "request_failed",
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "duration_ms": duration_ms,
                },
                ensure_ascii=True,
            )
        )
        raise

    duration_ms = round((time.perf_counter() - started) * 1000, 2)
    completed_level = logging.DEBUG if is_low_noise else logging.INFO

    _log_as_json(
        request_logger,
        completed_level,
        {
            "event": "request_completed",
            "request_id": request_id,
            "method": request.method,
            "path": path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )

    # Propagate the request_id back to the caller as a response header
    response.headers["X-Request-Id"] = request_id
    return response
