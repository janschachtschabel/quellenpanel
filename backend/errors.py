"""errors.py — one error JSON shape for every API error (Diensteleitfaden: errors with trace id).

  {"error": <slug>, "message": <text>, "status": <int>, "trace_id": <id>}
  422 adds "details": [{loc, msg}] (never the rejected input); 500 never shows the exception text.
  UpstreamError (502/503/429) adds the Retry-After header and "retryAfter".
"""
from __future__ import annotations

import logging
from http import HTTPStatus

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

import obs

log = logging.getLogger("quellenpanel.errors")

DEFAULT_RETRY_AFTER = 30
_MAX_RETRY_AFTER = 86400
_SLUG_OVERRIDES = {413: "payload_too_large", 422: "validation_error", 500: "internal_error"}
INTERNAL_MESSAGE = "Interner Fehler"


class UpstreamError(HTTPException):
    """An upstream (repository) failure the client may retry after `retry_after` seconds."""

    def __init__(self, status_code: int, message: str, retry_after: int = DEFAULT_RETRY_AFTER):
        super().__init__(status_code, message, headers={"Retry-After": str(retry_after)})
        self.retry_after = retry_after


def parse_retry_after(value) -> int:
    """Seconds from a numeric Retry-After header within 0..86400, else the default."""
    try:
        n = int(str(value).strip())
    except (TypeError, ValueError):
        return DEFAULT_RETRY_AFTER
    return n if 0 <= n <= _MAX_RETRY_AFTER else DEFAULT_RETRY_AFTER


def slug(status: int) -> str:
    if status in _SLUG_OVERRIDES:
        return _SLUG_OVERRIDES[status]
    try:
        return HTTPStatus(status).name.lower()
    except ValueError:
        return "error"


def body(status: int, message: str, **extra) -> dict:
    return {"error": slug(status), "message": message, "status": status,
            "trace_id": obs.trace_id.get(), **extra}


def response(status: int, message: str, headers: dict | None = None, **extra) -> JSONResponse:
    return JSONResponse(body(status, message, **extra), status_code=status, headers=headers)


def internal_error_parts() -> tuple[int, list[tuple[bytes, bytes]], bytes]:
    """The 500 answer for obs.TraceMiddleware (status, raw headers, body bytes)."""
    r = response(500, INTERNAL_MESSAGE)
    return 500, list(r.raw_headers), bytes(r.body)


async def _http_exc(_request: Request, exc: StarletteHTTPException):
    status = exc.status_code
    message = exc.detail if isinstance(exc.detail, str) and exc.detail else HTTPStatus(status).phrase
    extra = {"retryAfter": exc.retry_after} if isinstance(exc, UpstreamError) else {}
    return response(status, message, headers=getattr(exc, "headers", None), **extra)


async def _validation(_request: Request, exc: RequestValidationError):
    details = [{"loc": list(e.get("loc", ())), "msg": str(e.get("msg", ""))} for e in exc.errors()]
    return response(422, "Ungültige Anfrage", details=details)


async def _unhandled(_request: Request, exc: Exception):
    log.error("Unbehandelter Fehler", exc_info=exc)
    return response(500, INTERNAL_MESSAGE)


def install(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, _http_exc)
    app.add_exception_handler(RequestValidationError, _validation)
    app.add_exception_handler(Exception, _unhandled)   # fallback; TraceMiddleware answers first
