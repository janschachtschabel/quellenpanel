"""Etappe 3 / Task 1: JSON logs, B3 tracing, one request line per request, no secrets in logs."""
import io
import json
import logging
import re

import pytest

import obs

HEX32 = re.compile(r"^[0-9a-f]{32}$")
T32 = "463ac35c9f6413ad48485a3953bb6124"
S16 = "a2fb4a1d1a96d312"


def _line(fmt: logging.Formatter, msg="hallo", **extra) -> str:
    rec = logging.LogRecord("quellenpanel", logging.INFO, __file__, 1, msg, None, None)
    for k, v in extra.items():
        setattr(rec, k, v)
    return fmt.format(rec)


def test_json_log_line_has_required_fields():
    d = json.loads(_line(obs.JsonFormatter(), fields={"route": "/x"}))
    for k in ("timestamp", "level", "service", "trace_id", "span_id", "message"):
        assert k in d
    assert d["service"] == "quellenpanel"
    assert d["level"] == "INFO"
    assert d["message"] == "hallo"
    assert d["route"] == "/x"
    assert d["timestamp"].endswith("Z")


def test_text_format_switch(monkeypatch):
    root = logging.getLogger()
    saved = root.handlers[:], root.level
    try:
        monkeypatch.setenv("LOG_FORMAT", "text")
        obs.setup_logging()
        ours = lambda: [h for h in root.handlers if getattr(h, "_qp", False)]  # noqa: E731
        line = ours()[0].formatter.format(
            logging.LogRecord("x", logging.INFO, __file__, 1, "hallo", None, None))
        with pytest.raises(json.JSONDecodeError):
            json.loads(line)
        monkeypatch.setenv("LOG_FORMAT", "json")
        obs.setup_logging()
        obs.setup_logging()                       # idempotent: still exactly one handler
        assert len(ours()) == 1                   # foreign handlers (e.g. pytest's) are kept
        assert isinstance(ours()[0].formatter, obs.JsonFormatter)
    finally:
        root.handlers[:] = saved[0]
        root.setLevel(saved[1])


def test_parse_b3_valid_and_single_header():
    assert obs.parse_b3({"X-B3-TraceId": T32, "X-B3-SpanId": S16, "X-B3-Sampled": "1"}) == (T32, S16, "1")
    assert obs.parse_b3({"x-b3-traceid": T32[:16], "x-b3-spanid": S16}) == (T32[:16], S16, None)
    assert obs.parse_b3({"b3": f"{T32}-{S16}-1"}) == (T32, S16, "1")
    assert obs.parse_b3({"b3": f"{T32}-{S16}"}) == (T32, S16, None)


@pytest.mark.parametrize("headers", [
    {"X-B3-TraceId": T32[:31], "X-B3-SpanId": S16},
    {"X-B3-TraceId": "zz" + T32[2:], "X-B3-SpanId": S16},
    {"X-B3-TraceId": "a" * 1000, "X-B3-SpanId": S16},
    {"X-B3-TraceId": T32, "X-B3-SpanId": S16[:15]},
    {"X-B3-TraceId": T32.upper(), "X-B3-SpanId": S16},
    {"X-B3-TraceId": T32, "X-B3-SpanId": S16, "X-B3-Sampled": "yes"},
    {"b3": "kaputt"},
    {"b3": f"{T32}-{S16}-1-{S16}-x"},
    {},
])
def test_parse_b3_rejects_garbage(headers):
    assert obs.parse_b3(headers) is None


def test_request_gets_trace_and_echoes(client):
    r = client.get("/api/health")
    assert HEX32.match(r.headers["X-B3-TraceId"])
    r = client.get("/api/health", headers={"X-B3-TraceId": T32, "X-B3-SpanId": S16})
    assert r.headers["X-B3-TraceId"] == T32
    r = client.get("/api/health", headers={"X-B3-TraceId": "zz", "X-B3-SpanId": S16})
    assert HEX32.match(r.headers["X-B3-TraceId"]) and r.headers["X-B3-TraceId"] != T32
    r = client.get("/api/health", headers={"x-client-trace-id": "widget-42.a_b"})
    assert r.headers["x-client-trace-id"] == "widget-42.a_b"
    r = client.get("/api/health", headers={"x-client-trace-id": "<script>"})
    assert "x-client-trace-id" not in r.headers


def _request_lines(caplog):
    return [r for r in caplog.records if r.getMessage() == "request"]


def test_one_request_line_with_route_class(client, caplog):
    caplog.set_level(logging.INFO)
    caplog.clear()
    client.get("/api/sources/node:abc?q=Geheimwort")
    lines = _request_lines(caplog)
    assert len(lines) == 1
    f = lines[0].fields
    assert f["route"] == "/api/sources/{source_id:path}"
    assert f["method"] == "GET"
    assert isinstance(f["status"], int)
    assert f["duration_ms"] >= 0
    assert f["q_pseudonym"] == obs.pseudonym("Geheimwort")


def test_unmatched_route_class(client, caplog):
    caplog.set_level(logging.INFO)
    caplog.clear()
    client.get("/api/gibtsnicht/abc")
    lines = _request_lines(caplog)
    assert len(lines) == 1
    assert lines[0].fields["route"] in ("<unmatched>", "<static>")
    assert "abc" not in lines[0].fields["route"]


def test_no_secrets_in_logs(client, caplog, monkeypatch):
    from fastapi.routing import APIRoute

    import app as app_module

    def boom():
        raise RuntimeError("kaputt")

    app_module.app.router.routes.insert(0, APIRoute("/api/__test_boom", boom))  # before the static mount
    try:
        caplog.set_level(logging.DEBUG)
        for name in ("httpx", "httpx2"):                    # the TEST client's own URL log
            monkeypatch.setattr(logging.getLogger(name), "level", logging.WARNING)
        caplog.clear()
        h = {"X-Team-Password": "pw-XYZ", "X-Tier1-Password": "t1-XYZ"}
        client.cookies.set("qe_session", "sess-XYZ")
        client.get("/api/sources?q=Geheimwort", headers=h)
        client.get("/api/gibtsnicht?q=Geheimwort", headers=h)
        assert client.get("/api/__test_boom?q=Geheimwort", headers=h).status_code == 500  # answered, not raised
        text = caplog.text + " ".join(json.dumps(getattr(r, "fields", {})) for r in caplog.records)
        for secret in ("pw-XYZ", "t1-XYZ", "sess-XYZ", "Geheimwort"):
            assert secret not in text, secret
        statuses = [r.fields["status"] for r in _request_lines(caplog)]
        assert 500 in statuses
        assert any(r.fields.get("q_pseudonym") == obs.pseudonym("Geheimwort") for r in _request_lines(caplog))
    finally:
        app_module.app.router.routes[:] = [r for r in app_module.app.router.routes
                                           if getattr(r, "path", "") != "/api/__test_boom"]
        client.cookies.clear()


def test_pseudonym():
    assert obs.pseudonym("") == ""
    p = obs.pseudonym("Geheimwort")
    assert re.fullmatch(r"[0-9a-f]{12}", p) and p == obs.pseudonym("Geheimwort")


def test_outgoing_headers_propagate():
    assert obs.outgoing_headers() == {}
    with obs.trace_scope(T32, S16, "1", "cid-1"):
        h = obs.outgoing_headers()
        assert h["X-B3-TraceId"] == T32
        assert h["X-B3-ParentSpanId"] == S16
        assert re.fullmatch(r"[0-9a-f]{16}", h["X-B3-SpanId"]) and h["X-B3-SpanId"] != S16
        assert h["X-B3-Sampled"] == "1"
        assert h["x-client-trace-id"] == "cid-1"
    assert obs.outgoing_headers() == {}


def test_fetch_contents_sends_b3(monkeypatch):
    import wlo_content

    seen = {}

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        seen.update({k.lower(): v for k, v in req.header_items()})
        return Resp(b'{"nodes": []}')

    monkeypatch.setattr(wlo_content.urllib.request, "urlopen", fake_urlopen)
    with obs.trace_scope(T32, S16, None, None):
        wlo_content.fetch_contents("ccm:publisher", "X")
    assert seen["x-b3-traceid"] == T32


# --- Zwischenreview Etappe 3 ----------------------------------------------------------------
def test_413_and_preflight_carry_trace(client, caplog):
    caplog.set_level(logging.INFO)
    caplog.clear()
    r = client.post("/api/sources/batch", content=b"x", headers={"Content-Length": "99999999"})
    assert r.status_code == 413
    assert r.json()["trace_id"] == r.headers["X-B3-TraceId"]
    p = client.options("/api/sources", headers={"Origin": "https://x.example"})
    assert p.status_code == 204 and "X-B3-TraceId" in p.headers
    assert len(_request_lines(caplog)) == 2


def test_pseudonym_is_keyed_not_plain_sha256():
    import hashlib
    # A plain hash of a short search term can be reversed by trying a word list.
    assert obs.pseudonym("Geheimwort") != hashlib.sha256(b"Geheimwort").hexdigest()[:12]


def test_method_label_is_bounded():
    assert obs.method_label("GET") == "GET"
    assert obs.method_label("delete") == "DELETE"
    assert obs.method_label("FOOBAR") == "OTHER"
    assert obs.method_label(None) == "OTHER"


def test_unknown_method_does_not_create_new_metric_series(client):
    client.request("XYZZY", "/api/health")
    labels = {s.labels.get("method") for m in obs.REGISTRY.collect() if m.name == "http_requests"
              for s in m.samples}
    assert "XYZZY" not in labels


def test_probe_route_is_not_counted_or_logged(client, caplog):
    # The readiness probe hits /api/health every few seconds; counting it would water down the
    # 5xx ratio of quiet instances and flood the log.
    def count():
        return sum(s.value for m in obs.REGISTRY.collect() if m.name == "http_requests"
                   for s in m.samples if s.name == "http_requests_total" and s.labels.get("route") == "/api/health")

    caplog.set_level(logging.INFO)
    before = count()
    caplog.clear()
    client.get("/api/health")
    assert _request_lines(caplog) == []
    assert count() == before
