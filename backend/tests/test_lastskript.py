"""Etappe 7: Das Lastskript misst nur echte Antworten (bricht bei 503 ohne Daten ab)."""
import http.server
import importlib.util
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _modul():
    spec = importlib.util.spec_from_file_location("last", ROOT / "deploy/messung/last.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def _server(code: int):
    class H(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            self.send_response(code)
            self.send_header("content-type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"items": [{"id": "x"}]}')

        def log_message(self, *a):
            pass

    s = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


def test_lastskript_bricht_ab_wenn_instanz_503_liefert():
    s = _server(503)
    try:
        assert _modul().main([f"http://127.0.0.1:{s.server_port}", "--clients", "2", "--sekunden", "0.2"]) == 2
    finally:
        s.shutdown()


def test_lastskript_misst_bei_200():
    s = _server(200)
    try:
        assert _modul().main([f"http://127.0.0.1:{s.server_port}", "--clients", "2", "--sekunden", "0.3"]) == 0
    finally:
        s.shutdown()
