"""obs.py — structured logs and B3 tracing (Diensteleitfaden: JSON logs, trace propagation).

  setup_logging()     one root handler on stdout; LOG_FORMAT=json (default) | text, LOG_LEVEL
  JsonFormatter       one JSON object per line: timestamp, level, service, trace_id, span_id,
                      message, plus the dict in `extra={"fields": {...}}`
  parse_b3(headers)   validated B3 context (multi-header or single `b3`) or None
  TraceMiddleware     pure ASGI: trace context per request, X-B3-TraceId on the answer, one
                      `request` log line (method, route TEMPLATE, status, duration_ms,
                      q_pseudonym) — never the raw path, query, headers or cookies
  outgoing_headers()  B3 headers for an outgoing call made inside a request
"""
from __future__ import annotations

import contextlib
import contextvars
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import sys
import time
from collections.abc import Mapping
from datetime import datetime, timezone
from urllib.parse import parse_qs

from prometheus_client import REGISTRY as REGISTRY, Counter, Gauge, Histogram

SERVICE = "quellenpanel"

trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("trace_id", default=None)
span_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("span_id", default=None)
sampled: contextvars.ContextVar[str | None] = contextvars.ContextVar("sampled", default=None)
client_trace_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("client_trace_id", default=None)

_TRACE_RE = re.compile(r"^(?:[0-9a-f]{16}|[0-9a-f]{32})$")
_SPAN_RE = re.compile(r"^[0-9a-f]{16}$")
_SAMPLED = ("0", "1", "d")
_CLIENT_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_log = logging.getLogger("quellenpanel.request")

# ---------------------------------------------------------------- metrics (default registry)
HTTP_REQUESTS = Counter("http_requests_total", "HTTP-Anfragen", ["route", "method", "status"])
HTTP_DURATION = Histogram("http_request_duration_seconds", "Dauer der HTTP-Anfragen", ["route", "method"])
REBUILD_TOTAL = Counter("quellenpanel_rebuild_total", "Datenaufbau-Läufe", ["result"])
REBUILD_DURATION = Histogram("quellenpanel_rebuild_duration_seconds", "Dauer des Datenaufbaus",
                             buckets=(60, 300, 600, 1200, 1800, 3600, 7200, 14400, float("inf")))
REBUILD_LAST_SUCCESS = Gauge("quellenpanel_rebuild_last_success_timestamp_seconds",
                             "Zeitpunkt des letzten erfolgreichen Datenaufbaus")
DATA_AGE = Gauge("quellenpanel_data_age_seconds", "Alter des ausgelieferten Datenstands (NaN = keiner)")
EXPORT_FETCH = Counter("quellenpanel_export_fetch_total", "Abrufe des Exports", ["tier", "result"])
UPSTREAM = Counter("quellenpanel_upstream_requests_total", "Ausgehende Anfragen", ["target", "result"])


# ---------------------------------------------------------------- logging

class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc)
        out = {
            "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%S.") + f"{int(record.msecs):03d}Z",
            "level": record.levelname,
            "service": SERVICE,
            "logger": record.name,
            "trace_id": trace_id.get(),
            "span_id": span_id.get(),
            "message": record.getMessage(),
        }
        fields = record.__dict__.get("fields")
        if isinstance(fields, Mapping):
            for k, v in fields.items():
                out.setdefault(k, v)
        if record.exc_info:
            out["exception"] = self.formatException(record.exc_info)
        return json.dumps(out, ensure_ascii=False, default=str)


class _TextFormatter(logging.Formatter):
    def __init__(self):
        super().__init__("%(asctime)s %(levelname)s %(name)s %(message)s")

    def format(self, record: logging.LogRecord) -> str:
        line = super().format(record)
        fields = record.__dict__.get("fields")
        if isinstance(fields, Mapping):
            line += " " + " ".join(f"{k}={v}" for k, v in fields.items())
        return line


class _StdoutHandler(logging.StreamHandler):
    """Always writes to the CURRENT sys.stdout (survives stream swaps, e.g. under test capture)."""
    _qp = True

    @property
    def stream(self):
        return sys.stdout

    @stream.setter
    def stream(self, _value):
        pass


def setup_logging() -> None:
    """Install (or replace) this service's root handler. Idempotent; foreign handlers are kept."""
    root = logging.getLogger()
    for h in [h for h in root.handlers if getattr(h, "_qp", False)]:
        root.removeHandler(h)
    handler = _StdoutHandler()
    fmt = os.environ.get("LOG_FORMAT", "json").strip().lower()
    handler.setFormatter(_TextFormatter() if fmt == "text" else JsonFormatter())
    root.addHandler(handler)
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO").strip().upper() or "INFO")


# ---------------------------------------------------------------- tracing

def new_trace_id() -> str:
    return secrets.token_hex(16)


def new_span_id() -> str:
    return secrets.token_hex(8)


def _get(headers: Mapping[str, str], name: str) -> str | None:
    for k, v in headers.items():
        if k.lower() == name:
            return v
    return None


def parse_b3(headers: Mapping[str, str]) -> tuple[str, str, str | None] | None:
    """(trace_id, parent_span_id, sampled) from valid B3 headers, else None."""
    single = _get(headers, "b3")
    if single is not None:
        parts = single.strip().split("-")
        if len(parts) not in (2, 3, 4):
            return None
        tid, sid = parts[0], parts[1]
        smp = parts[2] if len(parts) > 2 else None
        if len(parts) == 4 and not _SPAN_RE.match(parts[3]):
            return None
    else:
        tid, sid = _get(headers, "x-b3-traceid"), _get(headers, "x-b3-spanid")
        smp = _get(headers, "x-b3-sampled")
        if tid is None or sid is None:
            return None
    if not (_TRACE_RE.match(tid) and _SPAN_RE.match(sid)):
        return None
    if smp is not None and smp not in _SAMPLED:
        return None
    return tid, sid, smp


@contextlib.contextmanager
def trace_scope(tid: str, sid: str, smp: str | None = None, cid: str | None = None):
    """Set the trace context for the block (requests, background jobs, tests)."""
    tokens = [(trace_id, trace_id.set(tid)), (span_id, span_id.set(sid)),
              (sampled, sampled.set(smp)), (client_trace_id, client_trace_id.set(cid))]
    try:
        yield
    finally:
        for var, tok in reversed(tokens):
            var.reset(tok)


def outgoing_headers() -> dict[str, str]:
    """B3 headers for an outgoing call (a new child span); {} outside any trace context."""
    tid = trace_id.get()
    if not tid:
        return {}
    h = {"X-B3-TraceId": tid, "X-B3-SpanId": new_span_id()}
    if span_id.get():
        h["X-B3-ParentSpanId"] = span_id.get()
    if sampled.get():
        h["X-B3-Sampled"] = sampled.get()
    if client_trace_id.get():
        h["x-client-trace-id"] = client_trace_id.get()
    return h


# Per-process key: a plain hash of a short search term could be reversed with a word list.
_PSEUDONYM_KEY = secrets.token_bytes(32)

# The readiness probe hits this every few seconds; counting it would water down the 5xx ratio.
_PROBE_ROUTES = frozenset({"/api/health"})

_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})


def pseudonym(value: str) -> str:
    """Stable within a process, not reversible: first 12 hex of HMAC-SHA256; '' stays ''."""
    if not value:
        return ""
    return hmac.new(_PSEUDONYM_KEY, value.encode("utf-8"), hashlib.sha256).hexdigest()[:12]


def method_label(method: str | None) -> str:
    """Bounded label for logs and metrics: known HTTP methods, everything else is OTHER."""
    m = (method or "").upper()
    return m if m in _METHODS else "OTHER"


def _route_of(scope) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    if path:
        return path
    endpoint = scope.get("endpoint")
    if endpoint is not None and type(endpoint).__name__ == "StaticFiles":
        return "<static>"
    return "<unmatched>"


class TraceMiddleware:
    """Pure ASGI middleware: trace context, response trace headers and one request log line."""

    def __init__(self, app, on_error=None):
        self.app = app
        # on_error() -> (status, raw headers, body): the answer to an unhandled exception, sent HERE
        # so it still carries the trace context and headers (ServerErrorMiddleware sits outside).
        self.on_error = on_error

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = {k.decode("latin-1"): v.decode("latin-1") for k, v in scope.get("headers", [])}
        b3 = parse_b3(headers)
        tid, _parent, smp = b3 if b3 else (new_trace_id(), None, None)
        cid = headers.get("x-client-trace-id")
        cid = cid if cid and _CLIENT_ID_RE.match(cid) else None
        status = {"code": 500, "started": False}
        extra_headers = [(b"x-b3-traceid", tid.encode())]
        if cid:
            extra_headers.append((b"x-client-trace-id", cid.encode()))

        async def _send(message):
            if message["type"] == "http.response.start":
                status["code"], status["started"] = message["status"], True
                message = {**message, "headers": [*message.get("headers", []), *extra_headers]}
            await send(message)

        start = time.perf_counter()
        sid = new_span_id()
        with trace_scope(tid, sid, smp, cid):
            try:
                await self.app(scope, receive, _send)
            except Exception:
                if status["started"] or self.on_error is None:
                    raise
                _log.error("Unbehandelter Fehler", exc_info=True)
                code, raw_headers, payload = self.on_error()
                await _send({"type": "http.response.start", "status": code, "headers": raw_headers})
                await _send({"type": "http.response.body", "body": payload})
            finally:
                q = (parse_qs(scope.get("query_string", b"").decode("latin-1")).get("q") or [""])[0]
                fields = {"method": method_label(scope.get("method")), "route": _route_of(scope),
                          "status": status["code"],
                          "duration_ms": round((time.perf_counter() - start) * 1000, 1)}
                if q.strip():
                    fields["q_pseudonym"] = pseudonym(q.strip())
                if not (fields["route"] in _PROBE_ROUTES and status["code"] < 500):  # probe: skip
                    _log.info("request", extra={"fields": fields})
                    HTTP_REQUESTS.labels(fields["route"], fields["method"], str(fields["status"])).inc()
                    HTTP_DURATION.labels(fields["route"], fields["method"]).observe(fields["duration_ms"] / 1000)
