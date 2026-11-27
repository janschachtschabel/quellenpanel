# Etappe 3: Betrieb nach Diensteleitfaden – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quellenpanel läuft als betreibbarer Dienst nach dem Diensteleitfaden.

**Architecture:** Neue, kleine Module tragen die Querschnittsthemen:
- `obs.py`: Logs, B3-Tracing und Metriken.
- `errors.py`: Fehlerformat.
- `internal_app.py`: Port 9090.
- `serve.py`: startet beide Ports in einem Prozess.
- `bootstrap.py`: Erststart, Seed und Rebuild-Status.

Die Fachmodule rufen nur deren Helfer auf, z. B. `obs.outgoing_headers()` bei jedem Upstream-Aufruf.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, `prometheus-client` (neu), Helm 3, Prometheus-Regeln (`promtool`), GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-26-quellenpanel-produktiv-design.md` (§7 Diensteleitfaden, §8 Etappe 3, §9 Daten aus dem Image)

## Global Constraints

- Dienst-ID: `quellenpanel` (Log-Feld `service`, `OTEL_SERVICE_NAME`, Chart, Image).
- Logs: JSON nach stdout mit `timestamp, level, service, trace_id, span_id, message`. Klartext per `LOG_FORMAT=text`, Stufe per `LOG_LEVEL`. Pro Anfrage eine Zeile, mit der Routenklasse statt des Pfads. Das uvicorn-Access-Log ist aus.
  - Nie Passwörter oder Header-Werte loggen.
  - Suchbegriffe nur pseudonymisiert.
- B3 wird gelesen, geprüft und an Repository und Team-Instanz weitergegeben, sonst neu angelegt. `x-client-trace-id` wird durchgereicht.
- Fehler als JSON mit `trace_id`; 4xx und 5xx sauber getrennt; `retryAfter`, wenn eine Abhängigkeit mit 429/5xx antwortet.
- OpenAPI enthält nur die öffentlichen Pfade der jeweiligen Rolle.
- Ports:
  - **8080** öffentlich: API, SPA, Widgets.
  - **9090** intern: `/health`, `/ready`, `/metrics`; beim Team zusätzlich `/internal/exports/…`.
- Readiness hängt von keiner Abhängigkeit ab. `/ready` prüft die Quelle (Repository bzw. Export-Quelle) höchstens alle 30 s.
- `X-Forwarded-For` wird nur mit `TRUST_PROXY` ausgewertet.
- Team-Sitzung als signiertes Cookie (HMAC, `QE_SESSION_SECRET`) statt im Prozess-Speicher.
- SIGTERM beendet sauber; ein laufender Rebuild schreibt seinen Status. `/health` zeigt den Stand der Daten.
- `truth.json` liegt nicht mehr im Image.
  - Die Team-Instanz erzeugt sie auf dem Volume.
  - Erster Start ohne Daten → einmaliger Abruf mit Status „Daten werden aufgebaut“.
  - Optional Seed per `QE_SEED_URL`.
- `profiles/wlo/` im Image enthält nur `profil.toml`; `crawler.csv` und `korrekturen.csv` sind per `.dockerignore` ausgeschlossen.
- Der nächtliche Rebuild läuft im Team-Pod (`QE_AUTO_REFRESH_HOUR`). Alarm: „seit 26 h kein erfolgreicher Rebuild“.
- Dockerfile:
  - multi-stage, nicht root;
  - read-only rootfs plus `/tmp`;
  - Basis-Image per Digest.
- Chart `deploy/helm/quellenpanel`:
  - `version = appVersion` (mit Test);
  - Werte für alle Env-Variablen mit `## @param`;
  - Wert `role` mit `values-public.yaml`, `values-partner.yaml`, `values-team.yaml`;
  - PVC nur bei `team`;
  - NetworkPolicy (Standard aus), ServiceMonitor, PrometheusRule (mit `promtool test rules`);
  - Pod Security „restricted“.
- CI:
  - lint, Tests, `pip-audit`, `npm audit`;
  - `helm lint --strict`, `kubeconform`;
  - Tag = Version in `package.json` und `pyproject`.
- Compose-Referenz mit drei Diensten.
- Vercel-Pfad entfernen (`vercel.json`, `backend/api/`).
- Lint mit `python -m ruff check .` (ruff 0.12.9); Golden-, Neutralitäts-, Export- und alle bisherigen Tests bleiben grün.
- Arbeitsweise (Jan): Zwischenreview nach Task 4, Abschlussreview am Ende, Befunde per Test beheben.

## Review Focus

1. **Geheimnisse im Log:** Passwort-Header, Session-Cookie, `q`-Suchbegriff und Query-Strings tauchen in keiner Logzeile auf, auch nicht bei Fehlern und 500ern. Test in Task 1.
2. **Kaputter oder fremder B3-Header** (zu lang, keine Hex-Zeichen, falsche Länge) → wird verworfen und neu angelegt, nie ungeprüft ins Log oder an den Upstream gegeben. Test in Task 1.
3. **Gefälschtes oder abgelaufenes Session-Cookie**, ein Cookie mit fremdem Secret, oder ein Neustart mit anderem `QE_SESSION_SECRET` → kein Team-Zugang. Mit gleichem Secret überlebt die Sitzung den Neustart. Test in Task 4.
4. **Erststart ohne Daten:** Die Team-Instanz ist sofort live (`/health` 200), meldet aber „nicht bereit“ (`/ready` 503) und beantwortet die API mit 503 „Daten werden aufgebaut“, bis der Abruf fertig ist. Schlägt der Abruf fehl, bleibt der Status lesbar. Test in Task 5.
5. **Port-Trennung:** `/internal/exports`, `/metrics`, `/ready` sind auf 8080 nicht erreichbar (404). Auf 9090 gibt es keine öffentliche API. Test in Task 3.

---

## File Structure

| Datei | Verantwortung |
|---|---|
| `backend/obs.py` (neu) | Log-Setup (JSON/Text), Trace-Kontext (contextvars), B3 lesen/prüfen/erzeugen, `outgoing_headers()`, Pseudonymisierung, Prometheus-Metriken |
| `backend/errors.py` (neu) | Exception-Handler: einheitliches Fehler-JSON, `retryAfter` |
| `backend/internal_app.py` (neu) | FastAPI-App für Port 9090: `/health`, `/ready`, `/metrics`, `/internal/exports/…` |
| `backend/serve.py` (neu) | startet 8080 (`app:app`) und 9090 (`internal_app:app`) in einem Prozess, sauberes SIGTERM |
| `backend/bootstrap.py` (neu) | Erststart: Seed (`QE_SEED_URL`), Rebuild im Hintergrund, Statusdatei `$QE_DATA_DIR/status.json` |
| `backend/session.py` | signierte Tokens (HMAC) |
| `backend/ratelimit.py` | `client_ip` mit `TRUST_PROXY` |
| `backend/app.py`, `refresh.py`, `fetcher.py`, `wlo_content.py`, `thumb.py`, `export_store.py` | Middleware/Handler einbinden, B3 nach außen, Metriken, `/internal/exports` wandert nach 9090 |
| `backend/pyproject.toml` (neu) | `[project] name, version` (eine Versionsquelle für das Backend) |
| `Dockerfile`, `.dockerignore`, `deploy/docker-compose*.yml` | Härtung, Daten raus, drei Dienste |
| `deploy/helm/quellenpanel/**` | Chart nach Leitfaden |
| `.github/workflows/ci.yml` (neu), `docker-publish.yml` | CI-Gates, Tag-Prüfung |
| entfernt: `vercel.json`, `backend/api/` | Vercel-Pfad |

---

### Task 1: Logs und Tracing

**Files:** Create `backend/obs.py`; Modify `backend/app.py` (Middleware, Logging im Lifespan ersetzen), `fetcher.py`, `wlo_content.py`, `thumb.py`, `export_store.py` (ausgehende Header); Test `backend/tests/test_obs.py`

**Interfaces:**
- Produces:
  - `obs.SERVICE = "quellenpanel"`
  - `obs.setup_logging() -> None` liest `LOG_FORMAT` (`json` Standard | `text`) und `LOG_LEVEL` (Standard `INFO`). Es ist idempotent und ersetzt die Root-Handler.
  - `obs.JsonFormatter` gibt eine JSON-Zeile mit `timestamp` (ISO-8601 UTC), `level`, `service`, `trace_id`, `span_id`, `message` aus; dazu die Felder aus `record.__dict__["fields"]`, falls gesetzt.
  - `obs.parse_b3(headers: Mapping[str, str]) -> tuple[str, str, str | None] | None` liefert `(trace_id, parent_span_id, sampled)`:
    - Gelesen werden `X-B3-TraceId`/`X-B3-SpanId`/`X-B3-Sampled` oder der Einzelheader `b3`.
    - Gültig sind trace_id mit 16 oder 32 Hex-Zeichen (klein), span_id mit 16 Hex-Zeichen, sampled `0`/`1`/`d`.
    - Alles andere ergibt `None`.
  - `obs.new_trace_id() -> str` (32 Hex) und `obs.new_span_id() -> str` (16 Hex)
  - `obs.trace_context` sind ContextVars: `trace_id`, `span_id`, `client_trace_id`.
  - `obs.outgoing_headers() -> dict[str, str]`:
    - setzt `X-B3-TraceId` (aktuelle Trace-ID), `X-B3-SpanId` (neue Kind-Span-ID), `X-B3-ParentSpanId` (aktuelle Span-ID) und `X-B3-Sampled`, falls bekannt;
    - setzt `x-client-trace-id`, falls gesetzt;
    - ohne Kontext ist das Ergebnis `{}`.
  - `obs.pseudonym(value: str) -> str` gibt die ersten 12 Hex-Zeichen von SHA-256 über `value` aus; leer bleibt leer.
  - `obs.TraceMiddleware` (reine ASGI- oder Starlette-Middleware):
    - setzt den Kontext aus B3 oder neu;
    - setzt die Antwortheader `X-B3-TraceId` und `x-client-trace-id`, Letzteren nur als Echo eines gültigen Werts (max. 64 Zeichen aus `[A-Za-z0-9._-]`);
    - loggt eine Zeile `request` mit `fields = {method, route, status, duration_ms, q_pseudonym?}`. `route` ist die Routen-Vorlage (`/api/sources/{source_id:path}`); unbekannte Pfade erscheinen als `"<unmatched>"`, statische Dateien als `"<static>"`.
- Consumes: —

- [ ] **Step 1: Failing tests** in `test_obs.py`:
  - `test_json_log_line_has_required_fields` (caplog bzw. Handler mit `JsonFormatter` auf `io.StringIO`): Alle sechs Pflichtfelder sind vorhanden, `service == "quellenpanel"`.
  - `test_text_format_switch` (`LOG_FORMAT=text`): Die Zeile ist kein JSON.
  - `test_parse_b3_valid_and_single_header`: Gültige Multi-Header werden gelesen; `b3: {trace}-{span}-1` auch.
  - `test_parse_b3_rejects_garbage` (Review Focus 2): Trace-ID mit 31 Zeichen, mit `zz…`, mit 1000 Zeichen und Span-ID mit 15 Zeichen ergeben jeweils `None`.
  - `test_request_gets_trace_and_echoes(client)`:
    - Ohne B3 kommt ein Antwortheader `X-B3-TraceId` mit 32 Hex zurück.
    - Mit gültigem B3 wird dieselbe Trace-ID zurückgegeben.
    - Mit kaputtem B3 kommt eine neue ID.
  - `test_one_request_line_with_route_class(client, caplog)`: `GET /api/sources/node:abc?q=Geheimwort` ergibt genau eine Zeile `request` mit `route == "/api/sources/{source_id:path}"`.
  - `test_no_secrets_in_logs(client, caplog)` (Review Focus 1):
    - Anfragen mit `X-Team-Password: pw-XYZ`, `X-Tier1-Password: t1-XYZ`, Cookie `qe_session=sess-XYZ`, `?q=Geheimwort`; außerdem ein 404 und ein provozierter 500 über eine Testroute per `monkeypatch`.
    - Prüfung: Keiner der Werte `pw-XYZ`, `t1-XYZ`, `sess-XYZ`, `Geheimwort` steht in `caplog.text`.
    - `obs.pseudonym("Geheimwort")` steht in einer Zeile.
  - `test_outgoing_headers_propagate`:
    - Im gesetzten Kontext ist `outgoing_headers()["X-B3-TraceId"]` die aktuelle Trace-ID, die SpanId neu und die ParentSpanId die aktuelle Span-ID.
    - Ohne Kontext ist das Ergebnis `{}`.
  - `test_fetch_contents_sends_b3(monkeypatch)`: In `wlo_content.fetch_contents` wird `urllib.request.urlopen` gefälscht. Der Request trägt `X-B3-TraceId`, wenn ein Kontext gesetzt ist.
- [ ] **Step 2:** Run `cd backend && python -m pytest tests/test_obs.py -q`. Expected: FAIL (`obs` fehlt).
- [ ] **Step 3: Implement.**
  - Der Lifespan ruft `obs.setup_logging()` statt `logging.basicConfig`. Die bestehende Prüfung „Host hat Handler“ entfällt: Logging-Setup ist Sache des Dienstes.
  - Die ausgehenden Aufrufe (fetcher: `H = {**H, **obs.outgoing_headers()}` je Aufruf; wlo_content; thumb; export_store) bekommen die Header.
- [ ] **Step 4:** Run `python -m pytest -q && python -m ruff check .`. Expected: grün.
- [ ] **Step 5: Commit** `feat: JSON-Logs, B3-Tracing und eine Logzeile je Anfrage`

### Task 2: Fehlerformat, retryAfter, OpenAPI je Rolle

**Files:** Create `backend/errors.py`; Modify `backend/app.py`; Test `backend/tests/test_errors.py`

**Interfaces:**
- Consumes: `obs.trace_context`
- Produces:
  - `errors.install(app: FastAPI) -> None` registriert Handler für `HTTPException`, `RequestValidationError` und `Exception`. Body: `{"error": <code>, "message": <Text>, "status": <int>, "trace_id": <id>}`.
    - `code`: Klein-Slug aus dem Status, z. B. `not_found`, `forbidden`, `unauthorized`, `too_many_requests`, `bad_request`, `validation_error`, `bad_gateway`, `service_unavailable`, `internal_error`.
    - 422 gibt zusätzlich `details`: Liste aus `{loc, msg}` ohne Eingabewerte.
    - 500 gibt nur `message: "Interner Fehler"`, nie den Exception-Text; der Stacktrace geht ins Log.
  - `errors.UpstreamError(HTTPException)` mit `status_code` 502/503/429 und `retry_after: int`. Antwort mit Header `Retry-After` und Feld `retryAfter`.
    - `/api/sources/{id}/contents` wirft ihn bei Upstream-Fehlern (Standard 30 s).
    - Bei `HTTPError` mit 429 aus dem Repository gilt dessen `Retry-After`, wenn es eine Zahl ist.
  - `app.openapi()` enthält nur Pfade der aktuellen Rolle:
    - Außerhalb von `team` fehlen `/api/stats/team`, `/api/protokoll.*`, `/jobs/refresh`, `/api/admin/reload` und `/api/auth`.
    - `/internal/*` fehlt immer, weil es auf Port 9090 liegt.
    - `info.title = "Quellenpanel"`, `info.description` erklärt Stufen und Rollen in einem Absatz, `info.version` = Backend-Version (Task 8; bis dahin `"0.3.0"` aus `pyproject.toml`).
  - Frontend: prüfen, ob es irgendwo `error.detail` liest; falls ja, auf `message` umstellen, mit Test.

- [ ] **Step 1: Failing tests:**
  - `test_404_json_has_trace_id(client)`: `/api/sources/gibts:nicht` liefert 404 mit `body["error"] == "not_found"`, `trace_id` gleich dem Antwortheader `X-B3-TraceId`, `status == 404`.
  - `test_422_without_input_echo(client)`: `/api/sources?page=0` liefert 422 mit `error == "validation_error"`, `details[0]["loc"]` und ohne Schlüssel `input`.
  - `test_500_hides_exception_text(client, monkeypatch)`: Eine Route wirft `RuntimeError("geheim-intern")`. Ergebnis: 500 mit `message == "Interner Fehler"`, ohne `"geheim-intern"` im Body (Client mit `raise_server_exceptions=False`).
  - `test_upstream_failure_has_retry_after(client, monkeypatch)`: `wlo_content.fetch_contents` wirft. `/api/sources/{id}/contents` liefert 502 mit Header `Retry-After: 30` und `retryAfter == 30`.
  - `test_openapi_per_role(client, monkeypatch)`:
    - Bei `team` steht `/api/stats/team` in `paths`.
    - Bei `QE_ROLE=public` (Schema-Cache leeren, `app.openapi_schema = None`) fehlt es, und `/internal/exports/stufe{tier}.json` fehlt in beiden Rollen.
- [ ] **Step 2:** Run `python -m pytest tests/test_errors.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** `app.openapi` wird überschrieben und filtert die Pfade nach `config.role()`. Der Cache gilt pro Rolle (`_openapi_cache: dict[str, dict]`).
- [ ] **Step 4:** Run `python -m pytest -q && python -m ruff check .`. Expected: grün. Die bestehenden Tests, die `detail` lesen, werden auf `message` umgestellt; jede Umstellung kommt ins Ledger.
- [ ] **Step 5: Commit** `feat: einheitliches Fehler-JSON mit trace_id, Retry-After, OpenAPI je Rolle`

### Task 3: Port 9090 – health, ready, metrics, interne Exporte

**Files:** Create `backend/internal_app.py`, `backend/serve.py`; Modify `backend/app.py` (`/internal/exports` und `/api/health` umziehen; `/api/health` bleibt als Alias auf 8080 für bestehende Einbettungen), `obs.py` (Metriken), `refresh.py`, `export_store.py`, `requirements.txt` (`prometheus-client==0.26.0`); Test `backend/tests/test_internal_app.py`

**Interfaces:**
- Consumes: `export_store`, `store._DATA`, `refresh.status()`, `config.role()`
- Produces:
  - `internal_app.app` (FastAPI, ohne OpenAPI-UI) mit:
    - `GET /health`: immer 200, solange der Prozess lebt. Body `{"status": "ok", "role", "version", "data": {"state": "ready"|"building"|"missing", "generatedAt", "ageSeconds"}, "rebuild": refresh.status()}`.
    - `GET /ready`: 200, wenn die Daten der Rolle im Speicher sind (Team: `_DATA["records"]` nicht leer; sonst alle Exporte der Rolle), sonst 503. Body enthält zusätzlich `"source": {"ok": bool, "checkedAt": iso}` aus einer Prüfung, die höchstens alle 30 s läuft:
      - Team: `HEAD`/`GET` auf `config.REPO_URL`.
      - Sonst: auf `config.export_source()` mit `tier=0`.
      - Die Prüfung beeinflusst den Status-Code **nicht** (Readiness ohne Abhängigkeiten).
    - `GET /metrics`: `prometheus_client.generate_latest()`.
    - `GET /internal/exports/stufe{tier}.json`: aus Etappe 2 hierher verschoben, nur in der Rolle `team`.
  - `obs` Metriken:
    - `http_requests_total{route,method,status}` und `http_request_duration_seconds{route,method}` (Histogram), beide aus der TraceMiddleware befüllt.
    - `quellenpanel_rebuild_total{result}` und `quellenpanel_rebuild_duration_seconds`.
    - `quellenpanel_rebuild_last_success_timestamp_seconds`
    - `quellenpanel_data_age_seconds` (Gauge mit Callback aus `generatedAt`)
    - `quellenpanel_export_fetch_total{tier,result}` mit `ok|not_modified|error`
    - `quellenpanel_upstream_requests_total{target,result}` mit `target ∈ repository|export_source`
  - `serve.main()` startet zwei `uvicorn.Server` in einer asyncio-Schleife:
    - Port `QE_PORT` (8080) mit `app:app`, `lifespan="on"`;
    - Port `QE_INTERNAL_PORT` (9090) mit `internal_app:app`, `lifespan="off"`;
    - beide mit `access_log=False`, `proxy_headers=False`, `server_header=False`.
    - SIGTERM: beide Server bekommen `should_exit`; der Lifespan von 8080 läuft zu Ende.

- [ ] **Step 1: Failing tests:**
  - `test_health_ready_team(client)`: Auf dem internen Client (`TestClient(internal_app.app)`; das Team ist über `client` bereits geladen) liefert `/health` 200 mit `data.state == "ready"` und `ageSeconds` ≥ 0, `/ready` 200.
  - `test_ready_503_public_without_export(export_files, monkeypatch)`: Wie der Etappe-2-Test liefert `/ready` hier 503, `/health` 200.
  - `test_ready_source_check_cached(monkeypatch)`: Die Prüffunktion wird gefälscht und gezählt. Zwei `/ready` innerhalb von 30 s ergeben einen Aufruf. Mit `monotonic` + 31 s sind es zwei.
  - `test_metrics_exposed(client)`: Nach `GET /api/sources` enthält `/metrics` `http_requests_total{` mit `route="/api/sources"` und `quellenpanel_data_age_seconds`.
  - `test_port_separation(client)` (Review Focus 5):
    - Auf `app` liefern `/internal/exports/stufe0.json`, `/metrics` und `/ready` 404.
    - Auf `internal_app` liefern `/api/sources` 404 und `/internal/exports/stufe0.json` in der Rolle `team` 200.
  - `test_rebuild_metrics(monkeypatch, tmp_path)`: `refresh._run_refresh()` mit Stubs (wie in Etappe 2) erhöht `quellenpanel_rebuild_total{result="success"}`; mit einem werfenden Stub `result="error"`.
  - `test_serve_builds_two_servers(monkeypatch)`: `serve.build_servers()` ergibt zwei Configs mit Ports 8080/9090 und `access_log is False`.
- [ ] **Step 2:** Run `python -m pytest tests/test_internal_app.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Die Export-Tests aus Etappe 2, die `/internal/exports` auf `client` aufrufen, werden auf den internen Client umgestellt (im Ledger festhalten). `serve.build_servers()` gibt die beiden `uvicorn.Config` zurück, damit es ohne Netz testbar ist.
- [ ] **Step 4:** Run `python -m pytest -q && python -m ruff check .`. Expected: grün.
- [ ] **Step 5: Commit** `feat: interner Port 9090 mit health/ready/metrics und Exporten`

### Task 4: Signierte Sitzung und TRUST_PROXY

**Files:** Modify `backend/session.py`, `backend/config.py`, `backend/ratelimit.py`; Test `backend/tests/test_session.py`

**Interfaces:**
- Produces:
  - `config.session_secret() -> bytes` liest `QE_SESSION_SECRET`. Fehlt der Wert, wird pro Prozess einmal ein Zufallswert erzeugt und eine Warnung geloggt („Sitzungen überleben keinen Neustart“).
  - `config.trust_proxy() -> bool` liest `TRUST_PROXY` (`1/true/yes/on`).
  - `session.issue() -> str` liefert `"<exp>.<nonce>.<sig>"`:
    - `exp` = Epoch-Sekunden plus `TTL`;
    - `nonce` = 16 Byte urlsafe;
    - `sig` = HMAC-SHA256 (urlsafe-b64) über `"<exp>.<nonce>"`.
  - `session.valid(token) -> bool`:
    - prüft Form, Signatur (`hmac.compare_digest`), Ablauf und die Sperrliste;
    - wirft nie eine Exception.
  - `session.revoke(token)` legt die Nonce bis zum Ablauf in eine kleine Sperrliste im Speicher (Logout auf diesem Pod; dokumentierte Grenze).
  - `ratelimit.client_ip(request)`: mit `TRUST_PROXY` der **erste** Eintrag aus `X-Forwarded-For` (vom Proxy gesetzt), sonst `request.client.host`.

- [ ] **Step 1: Failing tests** (Review Focus 3):
  - `test_token_survives_restart_with_same_secret(monkeypatch)`: Bei `QE_SESSION_SECRET=s1` liefert `issue()`, danach wird der Speicher geleert (`session._revoked.clear()`, kein Token-Speicher mehr), und `valid()` ist `True`.
  - `test_other_secret_rejects`: Ein mit `s1` signiertes Token gilt unter `s2` nicht.
  - `test_tampered_and_garbage_rejected`: Ist die Signatur um ein Zeichen geändert, `exp` erhöht, oder das Token `"a.b"`, `""`, `"x"*5000` oder `None`, ist das Ergebnis jeweils `False`.
  - `test_expired_rejected(monkeypatch)`: `time.time` wird über TTL hinaus gesetzt → `False`.
  - `test_revoke_blocks_token`
  - `test_team_cookie_roundtrip(client, team_pw)`: Der Login setzt das Cookie, und danach liefert `/api/sources?tier=2` ohne Header Stufe 2.
  - `test_client_ip_trust_proxy(monkeypatch)`: Ohne `TRUST_PROXY` gilt `request.client.host`; mit `TRUST_PROXY=1` und `X-Forwarded-For: 203.0.113.9, 10.0.0.1` gilt `203.0.113.9`.
- [ ] **Step 2:** Run `python -m pytest tests/test_session.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.** Den Docstring von `session.py` (Skalierungs-Hinweis) aktualisieren.
- [ ] **Step 4:** Run `python -m pytest -q && python -m ruff check .`. Expected: grün.
- [ ] **Step 5: Commit** `feat: signierte Team-Sitzung (HMAC) und TRUST_PROXY`
- [ ] **Step 6: Zwischenreview** über Task 1–4 mit frischem Reviewer (fähigstes Modell, `code-reviewer.md`, mit Plan, Spec und Review Focus). Critical- und Important-Befunde jeweils per Test beheben, Minor-Befunde ins Ledger.

### Task 5: Daten aus dem Image, Erststart, Seed, Rebuild-Status, Vercel weg

**Files:** Create `backend/bootstrap.py`; Modify `backend/app.py` (Lifespan Team), `refresh.py`, `.dockerignore`, `config.py`; Delete `vercel.json`, `backend/api/`; Test `backend/tests/test_bootstrap.py`

**Interfaces:**
- Consumes: `refresh.start()`/`status()`, `store.load`, `config.data_dir()`, `obs.outgoing_headers()`
- Produces:
  - `config.seed_url() -> str` (`QE_SEED_URL`): Basis-URL, unter der `crawler.csv`, `korrekturen.csv` und optional `truth.json` liegen.
  - `bootstrap.seed(data_dir: Path) -> list[str]` lädt jede **fehlende** dieser drei Dateien von `seed_url()/<name>` ins Datenverzeichnis (atomar) und gibt die geladenen Namen zurück. 404 für `truth.json` ist kein Fehler. Vorhandene Dateien werden nie überschrieben.
  - `bootstrap.start_team() -> str` gibt `"ready"` oder `"building"` zurück:
    - Fehlt `truth.json` im Datenverzeichnis, wird zuerst `seed()` versucht.
    - Fehlt sie danach immer noch, startet `refresh.start()` im Hintergrund; Rückgabe `"building"`.
    - Sonst lädt `store.load()` und baut die Exporte; Rückgabe `"ready"`.
  - Ist der Zustand `"building"`, antworten alle Datenrouten auf 8080 mit 503 `{"error": "service_unavailable", "message": "Daten werden aufgebaut", "retryAfter": 60}`. `/internal`-`/health` meldet `data.state == "building"` und `/ready` 503.
  - `refresh._run_refresh` setzt nach Erfolg den Zustand `"ready"` (Exporte bauen, wie bisher).
  - `bootstrap.write_status(state: dict)` / `read_status()` nutzen `$QE_DATA_DIR/status.json` mit `{status, startedAt, finishedAt, error}`:
    - `refresh` schreibt bei Start, Ende und Fehler.
    - Der Lifespan-Ausstieg schreibt bei laufendem Job `status: "abgebrochen"`.
    - `/health` zeigt `read_status()` unter `rebuild.last`.
  - `.dockerignore` schließt aus: `backend/data/truth.json`, `backend/data/raw/`, `backend/data/exports/`, `profiles/*/daten/`.
  - Die Profil-Startdaten (`profiles/<id>/daten/`) bleiben im Repo und im lokalen Entwicklungsbetrieb der Rückfall (`config.crawler_csv_path()` unverändert).
  - Vercel: `vercel.json` und `backend/api/` werden gelöscht, README-Abschnitt Vercel entfernt; `.dockerignore`-Einträge zu Vercel entfallen.

- [ ] **Step 1: Failing tests** (Review Focus 4), mit leerem `QE_DATA_DIR`:
  - `test_first_start_building`: `refresh.fetcher.refresh_all` blockiert auf einem `threading.Event`; `truth.main` ist ein Stub.
    - Ein frischer `TestClient(app)` startet.
    - `/api/sources` liefert 503 mit `message == "Daten werden aufgebaut"`.
    - Intern liefern `/health` 200 mit `state == "building"` und `/ready` 503.
    - Danach wird das Event gesetzt (Stub `truth.main` kopiert die Fixture-`truth.json` ins Datenverzeichnis) und auf das Job-Ende gewartet (max. 5 s Polling von `refresh.status()`).
    - Am Ende liefert `/api/sources` 200 und `/ready` 200.
  - `test_first_start_failure_status_readable`: `refresh_all` wirft. `/health` zeigt `rebuild.last.status == "error"`; die API bleibt 503.
  - `test_seed_downloads_missing_only(monkeypatch, tmp_path)`:
    - `urllib.request.urlopen` wird gefälscht und liefert je Name Bytes; `truth.json` gibt 404.
    - Eine vorhandene `korrekturen.csv` bleibt unverändert.
    - Rückgabe `["crawler.csv"]`.
  - `test_status_written_on_shutdown_during_rebuild`: läuft ein Job (Event blockiert), schreibt der Lifespan-Ausstieg `abgebrochen`.
  - `test_dockerignore_excludes_data`: `.dockerignore` enthält die vier Muster.
  - `test_vercel_removed`: `vercel.json` und `backend/api` existieren nicht.
- [ ] **Step 2:** Run `python -m pytest tests/test_bootstrap.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4:** Run `python -m pytest -q && python -m ruff check .`. Expected: grün.
- [ ] **Step 5: Commit** `feat: Daten nicht mehr im Image – Erststart baut auf, Seed, Rebuild-Status; Vercel entfernt`

### Task 6: Dockerfile und Compose

**Files:** Modify `Dockerfile`, `deploy/docker-compose.yml`, `deploy/docker-compose.tls.yml`, `deploy/Caddyfile` (Port), `deploy/README.md`; Test `backend/tests/test_deploy_files.py`

**Interfaces:**
- Produces:
  - Dockerfile:
    - `FROM node:22-slim@sha256:<digest> AS frontend` und `FROM python:3.12-slim@sha256:<digest>`. Die Digests holst du per `docker buildx imagetools inspect`; geht das nicht (Docker-Hub-Drosselung), per Registry-API. Den Weg hältst du im Ledger fest.
    - `ENV QE_DATA_DIR=/data PYTHONDONTWRITEBYTECODE=1 LOG_FORMAT=json`
    - `EXPOSE 8080 9090`
    - `HEALTHCHECK` auf `http://127.0.0.1:9090/health`
    - `CMD ["python", "serve.py"]`
    - `/data` gehört `appuser`.
  - Compose-Referenz `deploy/docker-compose.yml` mit drei Diensten:
    - `team` (Volume `quellenpanel-data:/data`, `read_only: true`, `tmpfs: /tmp`)
    - `partner` (`QE_ROLE=partner`, `QE_EXPORT_SOURCE=http://team:9090/internal/exports/stufe{tier}.json`)
    - `public` (`QE_ROLE=public`)
    - Alle mit `read_only: true`, `tmpfs: [/tmp]`, `user: "10001"`.
    - Nur 8080 von partner und public wird veröffentlicht; team nur auf `127.0.0.1`.
  - `docker-compose.tls.yml` und `Caddyfile` folgen der neuen Aufteilung (Caddy → public:8080 und partner:8080, `TRUST_PROXY=1`).

- [ ] **Step 1: Failing test** `test_deploy_files.py`:
  - Das Dockerfile enthält zweimal `@sha256:`, `EXPOSE 8080 9090` und `serve.py`; es enthält kein `--port 8080` mehr (alte CMD).
  - Die Compose-Datei (YAML mit `yaml`, falls installiert, sonst Textprüfung) hat Dienste `team`, `partner` und `public`, alle mit `read_only: true`.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - Danach das Image bauen. In der Cloud geht das mit Proxy-CA über eine Scratch-Kopie; bei Docker-Hub-429 schichtest du auf das vorhandene Image, Ruling.
  - `docker compose up` aller drei Dienste mit `--read-only`-Äquivalent.
  - Prüfen:
    - team bereit nach dem Seed: `QE_SEED_URL` zeigt auf einen lokalen `python -m http.server` mit den Profil-Daten und `truth.json`.
    - public `/api/health` 200 und `9090/ready` 200.
    - Ein Schreibversuch außerhalb von `/data` und `/tmp` scheitert nicht im normalen Betrieb: das Log ist frei von `Read-only file system`.
- [ ] **Step 4:** Run `python -m pytest -q`. Expected: grün.
- [ ] **Step 5: Commit** `build: gehärtetes Image (Digest, read-only, zwei Ports) und Compose mit drei Diensten`

### Task 7: Helm-Chart nach Leitfaden

**Files:** Modify `deploy/helm/quellenpanel/**`; Create `values-public.yaml`, `values-partner.yaml`, `values-team.yaml`, `templates/pvc.yaml`, `templates/networkpolicy.yaml`, `templates/servicemonitor.yaml`, `templates/prometheusrule.yaml`, `tests/rules-test.yaml` (promtool); Test `backend/tests/test_chart.py` (statische Prüfungen ohne Helm-Binary)

**Interfaces:**
- Produces:
  - Chart-Name `quellenpanel`; `version == appVersion == "0.3.0"`.
  - Im `values.yaml` hat jeder Wert ein `## @param`. Werte für alle Env-Variablen:
    - `role`, `profile`
    - `tier1Password`/`teamPassword`/`sessionSecret`, als Secret oder `existingSecret`
    - `exportSource`, `exportPollMinutes`, `seedUrl`, `autoRefreshHour`
    - `allowedOrigins`, `trustProxy`
    - `log.format`, `log.level`
    - `repoUrl`, `searchUrl`
  - `deployment.yaml`:
    - zwei Container-Ports `http` 8080 und `internal` 9090;
    - Probes `livenessProbe` → `/health`:9090, `readinessProbe` → `/ready`:9090, `startupProbe` → `/health`;
    - `securityContext`: `runAsNonRoot`, `readOnlyRootFilesystem`, `allowPrivilegeEscalation: false`, `capabilities.drop: [ALL]`, `seccompProfile: RuntimeDefault`;
    - `emptyDir` `/tmp`;
    - bei `role == team`: `replicas: 1`, `strategy: Recreate`, PVC an `/data`;
    - sonst `replicas: {{ .Values.replicaCount }}` und `emptyDir` `/data`.
  - `service.yaml`: Port 8080 (`http`) und ein zweiter Service `-internal` mit 9090.
  - `networkpolicy.yaml` (`networkPolicy.enabled: false`): erlaubt nur Ingress auf 8080 von überall und auf 9090 nur von Pods mit Label `app.kubernetes.io/name: quellenpanel` sowie aus dem Monitoring-Namespace (Wert).
  - `servicemonitor.yaml` (`metrics.serviceMonitor.enabled`) und `prometheusrule.yaml` (`metrics.prometheusRule.enabled`) mit diesen Alarmen:
    - `QuellenpanelRebuildStale`: `time() - quellenpanel_rebuild_last_success_timestamp_seconds > 26*3600`, nur `role=team`.
    - `QuellenpanelHigh5xx`: 5xx-Anteil > 5 % über 10 min.
    - `QuellenpanelExportFetchFailing`: `increase(quellenpanel_export_fetch_total{result="error"}[30m]) > 0` und kein `ok`.
  - `tests/rules-test.yaml` für `promtool test rules` mit mindestens dem Rebuild-Alarm (feuert nach 26 h, nicht nach 25 h).

- [ ] **Step 1: Failing test** `test_chart.py` (PyYAML, falls vorhanden, sonst `pip install pyyaml` in requirements-dev):
  - `Chart.yaml`: `name == "quellenpanel"`, `version == appVersion`, und die Version ist gleich `[project].version` in `backend/pyproject.toml` und `version` in `frontend/package.json`.
  - Jeder Schlüssel auf oberster und zweiter Ebene im `values.yaml` hat einen `## @param`-Kommentar.
  - Die drei Beispiel-Values setzen `role` passend.
  - Die Templates enthalten `readOnlyRootFilesystem: true`, `containerPort: 9090` und `strategy` mit `Recreate` im Team-Zweig.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3: Implement.**
  - Danach, soweit die Werkzeuge verfügbar sind:
    - `helm lint --strict` und `helm template` für jede der drei Values;
    - die Ausgabe durch `kubeconform -strict -ignore-missing-schemas`;
    - `promtool test rules deploy/helm/quellenpanel/tests/rules-test.yaml`, mit den aus dem Template gerenderten Regeln in `tests/rules.yaml`, erzeugt per `helm template … | yq`; ohne Helm wird die Regeldatei statisch gepflegt.
  - Nicht verfügbare Werkzeuge hältst du im Ledger fest; die CI (Task 8) führt sie aus.
- [ ] **Step 4:** Run `python -m pytest -q`. Expected: grün.
- [ ] **Step 5: Commit** `deploy: Helm-Chart nach Leitfaden (Rollen, zwei Ports, PVC nur Team, Alarme)`

### Task 8: Version, CI, Doku

**Files:** Create `backend/pyproject.toml`, `.github/workflows/ci.yml`; Modify `frontend/package.json` (`version: "0.3.0"`), `backend/app.py` (`version` aus pyproject), `.github/workflows/docker-publish.yml` (Tag-Prüfung, Build mit Digest-Basis), `backend/requirements-dev.txt` (`ruff==0.12.9`, `pyyaml`), `README.md`, `deploy/README.md`, `deploy/helm/quellenpanel/README.md`, `docs/datenaufbereitung.md`; Create `docs/betrieb.md` (Env-/Secret-Liste, Ports, Probes, Metriken, Alarme, Erststart, Seed, Rebuild, Logs/Tracing, Begründung „ohne b-api“, „Rebuild im Team-Pod“)

**Interfaces:**
- Produces:
  - `config.VERSION` liest `[project].version` aus `backend/pyproject.toml` per `tomllib`. Fehlt die Datei im Image, gilt `"0.0.0"`; deshalb gehört `pyproject.toml` ins Image.
  - Die CI `ci.yml` läuft bei Push und PR und hat diese Jobs:
    - **python:** `ruff check`, `pytest`, `pip-audit`.
    - **frontend:** `npm ci`, `npm test`, `npm audit --omit=dev --audit-level=high`.
    - **chart:**
      - `helm lint --strict` für die drei Values;
      - `helm template | kubeconform -strict -ignore-missing-schemas -schema-location default`;
      - `promtool test rules`;
      - Versions-Prüfung (Chart = pyproject = package.json).
    - **tag (nur bei `v*`):** `GITHUB_REF_NAME == "v" + version`.
  - `docker-publish.yml` setzt `needs: ci` (bzw. ruft die CI als `workflow_call` auf) und taggt das Image mit der Version.

- [ ] **Step 1: Failing test** `test_version.py`: `config.VERSION == "0.3.0"` und `client.get("/openapi.json").json()["info"]["version"] == "0.3.0"`. `test_chart.py` prüft bereits die Gleichheit aller Versionen.
- [ ] **Step 2:** Run. Expected: FAIL.
- [ ] **Step 3: Implement**, dazu die Doku.
- [ ] **Step 4: Volle Prüfung:**
  - `cd backend && python -m ruff check . && python -m pytest -q`;
  - `cd frontend && npm test -- --watch=false && npx ng build`;
  - die YAML-Syntax der Workflows mit `python -c "import yaml…"` prüfen.
  - Expected: grün.
- [ ] **Step 5: Commit und Push** `ci: Gates nach Leitfaden, eine Versionsquelle; docs: Betrieb`; PR-Beschreibung um Etappe 3 ergänzen.
- [ ] **Step 6: Abschlussreview** über die ganze Etappe mit frischem Reviewer, Befundbehebung per Test, Bericht an Jan.
