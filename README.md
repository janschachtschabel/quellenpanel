# Quellenpanel — one WLO source app, three audience tiers

Quellenpanel merges the two previous WLO source apps — the end-user **Quellenliste** and the
team-facing **Quellensteckbriefe** — into a single application over the shared data-truth engine.
They had the same data-preparation core (a 1:1 copy, painful to maintain twice) and only slightly
different requirements, so the difference is modelled as three **access tiers** rather than two apps.

## The three tiers

| Tier | Audience | Sees | Access |
|---|---|---|---|
| **0** | end user (default) | clean public minimum — sources, filters, quality, example content; **no data problems, no provenance** | always open |
| **1** | Steckbrief creator ("Detailmodus") | richer public/technical metadata — provenance, confidence, field generation | open by default, **optional** password (`QE_TIER1_PASSWORD`) |
| **2** | team | internal fields, all data-problem flags, audit protocol, exports, live refresh | team password (`QE_TEAM_PASSWORD`) |

Each request is served at the **effective tier** = `min(requested, allowed)` (see `tiers.py`).

## Three instances from one image (`QE_ROLE`)

| Role | Max tier | Holds in memory | Reachable |
|---|---|---|---|
| `team` (default) | 2 | `truth.json` (merged records) → builds the tier exports `$QE_DATA_DIR/exports/stufe{0,1}.json` | internal only |
| `partner` | 1 | only the tier-0 + tier-1 exports | public; tier 1 (details, Steckbrief PDF) **only** with `QE_TIER1_PASSWORD` — unset ⇒ tier 1 stays shut |
| `public` | 0 | only the tier-0 export | public, embeddable |

Every answer below tier 2 — on every instance, the team one included — comes from the tier export,
which is built by the same serializer that defines the tier (`exports.py`, `export_query.py`). An
instance therefore cannot show more than its tier, even if an auth check were wrong. Partner/public
load their export from `QE_EXPORT_SOURCE` (the team's `/internal/exports/stufe{tier}.json` with
ETag, or a file path), re-fetch it every `QE_EXPORT_POLL_MINUTES`, keep the last valid copy on errors
and in `/tmp` (retrying every 15 s while they hold none), and report not ready (`/ready` on port 9090
503, `/api/health` 503) until they have one. Team-only routes (audit,
protocol, refresh, reload, login, `/internal/exports`) do not exist on partner/public (404).
`QE_PUBLIC_ONLY=1` is the transitional alias for `QE_ROLE=public`; combined with another role it is
refused at start. `field_policy.py` remains the single source of truth
for the public/internal split; the no-leak invariant is tested per tier.

## Architecture (backend)

```
backend/
  app.py          thin web layer — tier-gated routes
  tiers.py        access-tier model: effective_tier(request) = min(requested, allowed)
  serialize.py    one flat record, layered by tier (+ searchUrl)
                    tier 0 → enduser.card/detail   tier 1 → + KI/legal & field-generation
                    tier 2 → + internal, all flags, bind (list badges) & per-field provenance
                    + Bezugsquelle-family link: familyCount (card badge) / related (detail) — Audit-tier only
  config.py       env config (repo/search URLs, team/tier-1 passwords, public-only, refresh hour)
                    + data paths: data dir (QE_DATA_DIR) first, then the profile's starting data
  repo_profile.py the active repository profile (profiles/<id>/profil.toml) — property names,
                    special-case spiders, crawler-table columns, branding
  korrekturen.py  curated corrections: one long-format, semicolon-separated CSV (read/validate/write)
  korrektur_store.py / korrektur_import.py / crawler_upload.py / anwenden.py / team_routes.py
                  team area: edit/import/export corrections, replace the crawler table, history +
                  backups, recompute the merge from the raw caches after each change (/api/team/…)
  field_policy.py THE public/internal field + flag policy
  ── shared data-truth engine (from the Quellensteckbriefe app) ──
  truth*.py store.py filtering.py stats*.py protokoll.py fetcher.py refresh.py session.py wlo_content.py
  data/           truth.json snapshot · raw/ live API caches (git-ignored, rebuilt by the fetcher)
  tools/          migrate_korrekturen.py (one-off: old correction list + overlay → korrekturen.csv)
profiles/
  wlo/            profil.toml + daten/crawler.csv + daten/korrekturen.csv (WLO production profile)
  beispiel/       minimal foreign profile — proves the core carries no WLO constants
```

The generic core knows no repository specifics; everything repository-specific lives in a profile.
How a profile is built and how the correction CSV is maintained (Excel-friendly):
[`profiles/README.md`](profiles/README.md).

The data engine is reused unchanged; the new code is the tier model (`tiers.py`), the tiered
serializer (`serialize.py`), the merged `app.py`, and the tier additions in `config.py`.

How the data is assembled (live fetch + curated files → merged `truth.json` → hide/filter/overlay/tier
on serve): [`docs/datenaufbereitung.md`](docs/datenaufbereitung.md) (compact tables + process diagram).

## Run (development)

```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --port 8080 --reload        # → http://localhost:8080 (API only, dev)
python serve.py                             # as in the container: 8080 + internal port 9090
```

With `ng serve` (proxy on :4200) the team area's write calls need `QE_ALLOWED_ORIGINS=http://localhost:4200`:
the proxy rewrites the Host header, and writes with a foreign `Origin` are refused (CSRF guard).

Operations (ports, probes, metrics, alerts, logs/tracing, first start, secrets): see
[`docs/betrieb.md`](docs/betrieb.md).

In production the backend serves the built Angular SPA from `frontend/dist/browser` at `/` (one
container, like the previous apps). For the frontend in dev: `cd frontend && npm install && npm start`
(or `npm run build` to produce the SPA the backend serves).

## Configuration (environment)

All optional, with production defaults:

| Variable | Default | Purpose |
|---|---|---|
| `QE_TEAM_PASSWORD` | unset (team off) | enables tier 2 (team). Fail-closed: unset ⇒ no team access |
| `QE_ROLE` | `team` | instance role: `team`, `partner` or `public` (see above) |
| `QE_TIER1_PASSWORD` | unset (tier 1 open on `team`, **shut** on `partner`) | password for tier 1 |
| `QE_PUBLIC_ONLY` | off | transitional alias for `QE_ROLE=public` |
| `QE_EXPORT_SOURCE` | unset | partner/public: URL or path of the export with `{tier}`, e.g. `http://quellenpanel-team-internal:9090/internal/exports/stufe{tier}.json`. Unset ⇒ local development only: built once from a local `truth.json` |
| `QE_EXPORT_POLL_MINUTES` | `10` | partner/public: re-fetch interval (0 = off) |
| `QE_ALLOWED_ORIGINS` | unset (same-origin) | comma-separated origins allowed to use a credentialed (cookie) cross-origin **team login** when the panel is embedded on another origin (e.g. `https://wirlernenonline.de`). Public read access stays open to any origin regardless. Requires HTTPS |
| `QE_FRAME_ANCESTORS` | `*` (team: `'self'`) | space-separated CSP `frame-ancestors` for the `/embed/*` iframe pages |
| `QE_REPO_URL` | `https://redaktion.openeduhub.net` | edu-sharing repository base — all live queries + the thumb proxy |
| `QE_SEARCH_URL` | `https://suche.wirlernenonline.de` | WLO search base — the per-source "contents in search" link |
| `QE_AUTO_REFRESH_HOUR` | unset (off) | hour 0–23 for the optional nightly data rebuild (Docker) |
| `QE_PROFILE` | `wlo` | repository profile to load (`profiles/<id>/profil.toml`) |
| `QE_PROFILES_DIR` | `<repo>/profiles` | where profiles live (e.g. a mounted volume) |
| `QE_DATA_DIR` | `backend/data` (image: `/data`) | writable data dir: `truth.json`, `raw/` caches, `exports/`, `status.json`, and `crawler.csv` / `korrekturen.csv` that override the profile's starting data |
| `QE_SEED_URL` | unset | team, first start: base URL with `crawler.csv`, `korrekturen.csv`, `truth.json` for missing files |
| `QE_SESSION_SECRET` | random per process | HMAC key of the signed team session (set it so logins survive restarts) |
| `TRUST_PROXY` | off | client IP from the rightmost `X-Forwarded-For` entry (only behind a proxy that overwrites it) |
| `LOG_FORMAT` / `LOG_LEVEL` | `json` / `INFO` | JSON lines (or `text`) on stdout |
| `QE_PORT` / `QE_INTERNAL_PORT` | `8080` / `9090` | ports of `serve.py` |

**Repository neutrality:** the core reads every property name, vocabulary URL, special-case spider
and crawler-table column from the active profile (`QE_PROFILE`); `QE_REPO_URL`/`QE_SEARCH_URL`
override the profile's URLs. A test (`test_neutral.py`) keeps WLO strings out of the core, and
`profiles/beispiel` runs the full merge against a foreign metadata set. Still per repository (by
design): the data in `QE_DATA_DIR` (never in the image) and the profile's curated data
(`crawler.csv`, `korrekturen.csv`).

## API (tier in parentheses; `?tier=` requests a tier, capped to what is allowed)

```
GET  /api/health                       service + record count (alias; probes use :9090/health and /ready)
GET  /api/capabilities                 maxTier for the caller (drives the UI tier controls)
GET  /api/meta/filters                 filter vocabulary
GET  /api/sources                      list (0/1/2; familyCount badge + team filters flag/show_blacklist only at 2)
GET  /api/sources/{id}                 detail (0/1/2; + related sources of the same Bezugsquelle family, tier 2 only)
GET  /api/sources/{id}/contents        live example content (public)
GET  /api/stats                        statistics overview — end-user (0) · extended/full (1+)
GET  /api/stats/team                   data-problem / origin / fill-level addendum (team)
GET  /api/export.json | .csv           leak-safe flat export (tier 1+)
GET  /api/protokoll.md | .json | .csv  data-problem audit protocol (team) — .md readable (tables
                                       capped at 300/rubric), .json structured / .csv flat rows,
                                       both UNCAPPED for consumption by other applications
POST /api/sources/batch                several records at the tier — feeds the multi-source PDF
GET  /api/thumb                        preview-image proxy for the PDF (configured repo host only)
POST /api/auth · /api/logout · GET /api/auth/status     team login (httpOnly session cookie)
POST /jobs/refresh (team) · GET /jobs/latest            live data refresh
GET|POST /api/team/korrekturen · PUT|DELETE /api/team/korrekturen/{id}   corrections (team)
GET  /api/team/korrekturen.csv · /api/team/korrekturen/verlauf          download · change history
POST /api/team/korrekturen/import/vorschau · /api/team/korrekturen/import   CSV/JSON/XLSX import
POST /api/team/crawler/vorschau · /api/team/crawler                     replace the crawler table
GET  /api/kennzahl                     {quellen, inhalte} for the list filters (0) — widget key figure
GET  /embed/{name}                     iframe page of a widget (see docs/widgets.md)
GET  /widgets/…                        widget script, element bundle, test pages
```

Errors share one shape: `{"error", "message", "status", "trace_id"}` (+ `details` on 422,
`retryAfter` with a `Retry-After` header on upstream 502/429 and while the team builds its data).
The OpenAPI document (`/openapi.json`) lists only the paths of the running role. Internal port 9090:
`GET /health`, `/ready`, `/metrics`, `/internal/exports/stufe{0,1}.json` (team).

## Tests

```bash
python -m ruff check .                    # lint (repo root)
cd backend && python -m pytest -q         # tier model, no-leak invariant, exports, roles, logs/tracing,
                                          #   errors, internal port, sessions, first start, deploy files, chart
cd frontend && npm test -- --watch=false  # vitest
```

CI (`.github/workflows/ci.yml`) runs these plus `pip-audit`, `npm audit`, `helm lint`, kubeconform,
`promtool test rules` and the version check (pyproject = Chart = package.json; tag = `v` + version).

## Deployment

One image serves the API + the built SPA. Access tiers are configured purely via env (all optional;
unset ⇒ end-user-only, fail-closed):

| Variable | Effect |
|----------|--------|
| `QE_TEAM_PASSWORD` | enables tier 2 (Audit / team login) |
| `QE_ROLE` | `team` (default) · `partner` · `public` — see "Three instances from one image" |
| `QE_TIER1_PASSWORD` | password gate for tier 1 (Details); unset ⇒ open on `team`, shut on `partner` |
| `QE_EXPORT_SOURCE` / `QE_EXPORT_POLL_MINUTES` | partner/public: where to fetch the tier export, and how often |
| `QE_PUBLIC_ONLY=1` | transitional alias for `QE_ROLE=public` |
| `QE_ALLOWED_ORIGINS` | comma-separated origins allowed a credentialed cross-origin team login (embedded widget on another origin); needs HTTPS. Public read access is unaffected |
| `QE_REPO_URL` / `QE_SEARCH_URL` | point live queries + the search link at another repo (default = prod) |
| `QE_AUTO_REFRESH_HOUR` | optional nightly rebuild (0–23), team only |
| `QE_SESSION_SECRET` / `QE_SEED_URL` / `TRUST_PROXY` | see the configuration table above |

```bash
# Docker (build + run locally)
docker build -t quellenpanel .
docker run -p 8080:8080 -e QE_TEAM_PASSWORD=… quellenpanel
# or: cp deploy/.env.example deploy/.env && docker compose -f deploy/docker-compose.yml up -d
```

The repo is kept in **two remotes** and each has its own, self-contained CI:

- **GitHub** — `.github/workflows/docker-publish.yml`: runs the backend + frontend tests and
  dependency audits, then builds and pushes the image to **Docker Hub** (needs `DOCKERHUB_USERNAME`
  / `DOCKERHUB_TOKEN` secrets; tags `latest` on `main`, plus branch / short-SHA / SemVer for `v*`
  tags). Skips the build cleanly (pipeline stays green) when the secrets are absent.
- **GitLab** — `.gitlab-ci.yml`: ruff lint → tests + audits → build & push the image to a
  self-hosted registry → package & push the **Helm chart**. All registry/chart credentials come
  from GitLab CI/CD variables (`DOCKER_REGISTRY`, `HELM_REGISTRY`, …); the build/deploy stages skip
  (pipeline stays green) until those variables are set. The two platforms are independent — editing
  one never touches the other.

Deployment targets:

- **Server (Docker Compose)**: ready-made `deploy/docker-compose.yml` + `.env.example`, plus an
  automatic-HTTPS variant (`deploy/docker-compose.tls.yml` + `Caddyfile`, Let's Encrypt via
  nip.io/sslip.io, no own domain needed) — step-by-step in [`deploy/README.md`](deploy/README.md).
  Both start team, partner and public read-only; the TLS variant lets Caddy overwrite
  `X-Forwarded-For` and sets `TRUST_PROXY=1`, so the per-client rate limits key on the real client IP.
- **Kubernetes (Helm)**: `deploy/helm/quellenpanel` — one release per role (`values-team.yaml`,
  `values-partner.yaml`, `values-public.yaml`): two ports, probes on 9090, restricted security
  context, PVC only for the team, optional NetworkPolicy / ServiceMonitor / PrometheusRule. See
  [`deploy/helm/quellenpanel/README.md`](deploy/helm/quellenpanel/README.md).

## Status

- ✅ **Look (Etappe 6)** — edu-sharing 11 tokens (`frontend/src/_tokens.scss`, same names as
  edu-sharing), brand colours from the profile (`[branding]` → `/api/capabilities`), Open Sans
  self-hosted, tiles after the edu-sharing card anatomy, texts in the formal German "Sie",
  `npm run lint:design` (edu-sharing design rules, in CI) and an axe-core audit of all views
  (`frontend/scripts/a11y-audit.mjs`, WCAG 2.1 AA, 0 violations). Details: [`docs/a11y.md`](docs/a11y.md).

- ✅ **Widgets (Etappe 5)** — one light script (`quellenpanel-widgets.js`, ~14 KB, no dependencies)
  with list, plain list, top N per subject, key figure, single source and statistics elements; tiles
  and the whole app as Angular elements; every element also as an iframe page with height protocol.
  No cookies, CSP-friendly, host page untouched. Guide: [`docs/widgets.md`](docs/widgets.md).

- ✅ **Operations (Etappe 3)** — JSON logs + B3 tracing, one error shape with trace id, internal
  port 9090 (health/ready/metrics), signed sessions, data out of the image (seed / first-start build),
  hardened digest-pinned image, three-service Compose, Helm chart per role with alerts, CI gates,
  version 0.6.0 from `backend/pyproject.toml`. Details: [`docs/betrieb.md`](docs/betrieb.md).
- ✅ **Backend** — merged 3-tier API; ruff clean (`backend/ruff.toml`); no-leak
  invariant + `QE_PUBLIC_ONLY` hard cap verified; login/fetch rate limits (proxy-safe) + thumbnail
  SSRF guard tested; deps pinned + CVE-clean (`pip-audit`). The Bezugsquelle-family index (publisher
  + sub-channels, e.g. YouTube) drives the card badge + the detail "related sources" — Audit-tier
  only; family multiplicity is covered in the audit protocol (ZWEITDATENSATZ / BQ_SUBCHANNEL, guarded
  by test), exportable as readable .md and machine-readable .json/.csv.
- ✅ **Frontend** — Angular 21 web component (Material 3, i18n): tiles/list, search + sort on top, no
  sidebars, detail popup (with per-source PDF), tier toggles (Basisinfos / Details / Audit), tiered
  statistics (base + Details fill-levels + team problem groups/examples + an interactive engine
  merge-flow diagram), the Bezugsquelle-family badge on tiles/list & "Verwandte Quellen" (with node
  ids) in the detail (Audit-tier), a manual "Daten aktualisieren" button in the Audit tier (triggers
  the same live rebuild as the nightly job, with progress), and the client-side PDF exports (jspdf,
  lazy-loaded): the multi-source Steckbrief PDF (multi-select, Details + Audit) and a "Tabelle" table
  PDF of the current filtered list (next to CSV/JSON). 41 frontend tests green; build clean; shipped
  deps CVE-clean (`npm audit --omit=dev`).
- ✅ **Deployment** — Docker image (build + run verified) · GitHub Actions → Docker Hub ·
  GitLab CI → self-hosted registry + Helm chart (`helm lint` clean) · Compose (HTTP + automatic
  HTTPS) · Kubernetes (Helm).

The previous apps (`quellenliste-x`, `quellenerschliessung-app`) keep running unchanged until
quellenpanel is deployed.
