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
`QE_PUBLIC_ONLY=1` hard-caps everyone at tier 0, so a public / embedded deployment cannot serve
tier 1/2 data even if an auth check were wrong. `field_policy.py` remains the single source of truth
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
  field_policy.py THE public/internal field + flag policy
  ── shared data-truth engine (from the Quellensteckbriefe app) ──
  truth*.py store.py filtering.py stats*.py protokoll.py fetcher.py refresh.py session.py wlo_content.py
  data/           truth.json snapshot · curated inputs · source_supplements.json (overlay)
```

The data engine is reused unchanged; the new code is the tier model (`tiers.py`), the tiered
serializer (`serialize.py`), the merged `app.py`, and the tier additions in `config.py`.

How the data is assembled (live fetch + curated files → merged `truth.json` → hide/filter/overlay/tier
on serve): [`docs/datenaufbereitung.md`](docs/datenaufbereitung.md) (compact tables + process diagram).

## Run (development)

```bash
cd backend
pip install -r requirements.txt
uvicorn app:app --port 8080 --reload        # → http://localhost:8080
```

In production the backend serves the built Angular SPA from `frontend/dist/browser` at `/` (one
container, like the previous apps). For the frontend in dev: `cd frontend && npm install && npm start`
(or `npm run build` to produce the SPA the backend serves).

## Configuration (environment)

All optional, with production defaults:

| Variable | Default | Purpose |
|---|---|---|
| `QE_TEAM_PASSWORD` | unset (team off) | enables tier 2 (team). Fail-closed: unset ⇒ no team access |
| `QE_TIER1_PASSWORD` | unset (tier 1 open) | gate tier 1 behind a lighter password |
| `QE_PUBLIC_ONLY` | off | hard-cap everyone at tier 0 (public / embedded deployment) |
| `QE_ALLOWED_ORIGINS` | unset (same-origin) | comma-separated origins allowed to use a credentialed (cookie) cross-origin **team login** when the panel is embedded on another origin (e.g. `https://wirlernenonline.de`). Public read access stays open to any origin regardless. Requires HTTPS |
| `QE_REPO_URL` | `https://redaktion.openeduhub.net` | edu-sharing repository base — all live queries + the thumb proxy |
| `QE_SEARCH_URL` | `https://suche.wirlernenonline.de` | WLO search base — the per-source "contents in search" link |
| `QE_AUTO_REFRESH_HOUR` | unset (off) | hour 0–23 for the optional nightly data rebuild (Docker) |

**Repository neutrality:** `QE_REPO_URL`/`QE_SEARCH_URL` repoint every live query. NOT covered (by
design, must be maintained manually per repository): the bundled `data/truth.json` snapshot, the
curated blacklists baked into it, and the `source_supplements.json` overlay images.

## API (tier in parentheses; `?tier=` requests a tier, capped to what is allowed)

```
GET  /api/health                       service + record count
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
```

## Tests

```bash
cd backend && python -m pytest -q       # 44 tests: tier model, no-leak invariant per tier, route gating,
                                        #   login/fetch rate limits, SSRF guard, hidden-breakdown split,
                                        #   protocol exports (.json/.csv) + family-multiplicity guard
cd frontend && npm test -- --watch=false  # 41 tests: i18n, services, quality, selection, grid columns,
                                          #   PDF builders (content-asserted) + URL-safety helpers (vitest)
```

## Deployment

One image serves the API + the built SPA. Access tiers are configured purely via env (all optional;
unset ⇒ end-user-only, fail-closed):

| Variable | Effect |
|----------|--------|
| `QE_TEAM_PASSWORD` | enables tier 2 (Audit / team login) |
| `QE_TIER1_PASSWORD` | optional password gate for tier 1 (Details); unset ⇒ open |
| `QE_PUBLIC_ONLY=1` | hard-cap every request at tier 0 (public / embedded) |
| `QE_ALLOWED_ORIGINS` | comma-separated origins allowed a credentialed cross-origin team login (embedded widget on another origin); needs HTTPS. Public read access is unaffected |
| `QE_REPO_URL` / `QE_SEARCH_URL` | point live queries + the search link at another repo (default = prod) |
| `QE_AUTO_REFRESH_HOUR` | optional nightly rebuild (0–23; needs a writable FS) |

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
  The TLS variant runs uvicorn with `--forwarded-allow-ips` and lets Caddy overwrite
  `X-Forwarded-For`, so the per-client rate limits key on the real client IP.
- **Kubernetes (Helm)**: `deploy/helm/quellenpanel` — a single-replica `Deployment` (stateless;
  bundled snapshot, no PVC), ConfigMap + Secret for the `QE_*` env, Service + Ingress. See
  [`deploy/helm/quellenpanel/README.md`](deploy/helm/quellenpanel/README.md). `helm lint` clean.
- **Vercel** (`vercel.json`): the `/api` routes run as a Python function (`backend/api/index.py`),
  the SPA is built as a static site; set the env vars in the Vercel project settings.
  **Caveat:** the team session store (and the in-process rate limits) are per-process, so on a
  horizontally scaled / serverless host a follow-up request may hit another instance and be treated
  as logged-out. For reliable team login use a single-instance container deployment (Compose/Helm);
  the Vercel path is best suited to the public (tier-0 / `QE_PUBLIC_ONLY`) read-only mode.

## Status

- ✅ **Backend** — merged 3-tier API; 44 tests green; ruff clean (`backend/ruff.toml`); no-leak
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
  HTTPS) · Kubernetes (Helm) · Vercel.

The previous apps (`quellenliste-x`, `quellenerschliessung-app`) keep running unchanged until
quellenpanel is deployed.
