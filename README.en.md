# Quellenpanel

[Deutsch](README.md) · **English**

Quellenpanel shows the sources of an edu-sharing repository (default: WirLernenOnline): as a public
source list with widgets, as a source profile ("Steckbrief") for partners and as an internal audit
for the team. One image: as one instance that separates the tiers by password, or as three instances
with one access tier each. Version and
changes: [`CHANGELOG.md`](CHANGELOG.md) (German).

## Overview

| Tier | For whom | What you see | Where |
|---|---|---|---|
| **0 Basic** | everyone | sources, filters, quality features, example content, statistics | instance `public` (and all others) |
| **1 Details** | partners, profile authors | plus provenance, licences, field generation, export, profile PDF | instance `partner` with password; on `team` without password |
| **2 Audit** | team | plus internal fields, data problems, protocol, corrections, data refresh | instance `team` only, with team password |

Below tier 2 every instance answers only from its export. The public instance never holds tier 1
or tier 2 data in memory.

## Installation

**Try it locally** (Python 3.12, Node 22 or 26):

```bash
cd frontend && npm ci && npm run build && npm run build:element && npm run build:widgets && cd ..
cd backend && pip install -r requirements.txt
QE_TEAM_PASSWORD=secret python serve.py      # http://localhost:8080 (role team)
```

Without `QE_ROLE` the instance runs as `team`; that is meant for development only. On a first start
without data it builds the data from the repository (a few minutes; until then the data routes
answer 503) or loads starting data from `QE_SEED_URL`. In a container (Compose, Helm) the image carries no corrections or crawler table: set `QE_SEED_URL` or upload both files in the team area, otherwise the team builds no data.

**Server with Traefik** (a Docker server that already runs a Traefik proxy with Let's Encrypt, such
as a Docker panel with "compose from URL"): `docker-compose.yml` in the root folder starts one instance
that serves every tier on one port (tier 1 and 2 only with their password), builds the image from this
repository and needs no variable at all on the first start. Then set `DOMAIN` or `PORT` and the
passwords in `.env` (template `.env.example`) and deploy again. Separate partner and public instances
can be added with `SEPARATE_INSTANCES=1`. Step by step
in [`deploy/README.md`](deploy/README.md#server-with-traefik).

**Server with Docker Compose** (three instances from a published image, step by step in
[`deploy/README.md`](deploy/README.md)):

```bash
cp deploy/.env.example deploy/.env       # set IMAGE, passwords, ports
docker compose -f deploy/docker-compose.yml up -d
```

Team on `127.0.0.1:8082`, partner on `8081`, public on `8080`. A variant with automatic HTTPS
(Caddy) sits next to it.

**Kubernetes with Helm** (one release per role, details in
[`deploy/helm/quellenpanel/README.md`](deploy/helm/quellenpanel/README.md)):

```bash
helm upgrade --install quellenpanel-team    deploy/helm/quellenpanel -f deploy/helm/quellenpanel/values-team.yaml \
  --set config.existingSecret=quellenpanel-team-secrets
helm upgrade --install quellenpanel-partner deploy/helm/quellenpanel -f deploy/helm/quellenpanel/values-partner.yaml
helm upgrade --install quellenpanel-public  deploy/helm/quellenpanel -f deploy/helm/quellenpanel/values-public.yaml
```

Operations (ports, probes, metrics, alerts, logs, secrets, data updates):
[`docs/betrieb.md`](docs/betrieb.md). Measured resources: [`docs/messung.md`](docs/messung.md).
Handover to operations: [`docs/uebergabe/`](docs/uebergabe/README.md) (German).

## Usage

The app has three views: **tiles**, **list** and **statistics**. At the top: search, source type and
sorting; below: subject, educational level, content type, minimum number of contents and OER. A
click on a source opens its profile with example content from the repository.

At the top right you pick the tier (**Basic**, **Details**, **Audit**) and the language (DE/EN). In
Details and Audit several sources can be selected and exported as a profile PDF; the filtered list
is available as CSV, JSON or table PDF.

## Access tiers and protection

| What | How | Effect |
|---|---|---|
| Instance role | `QE_ROLE=team`, `partner` or `public` | caps the highest tier (2, 1, 0); always set it |
| Tier 1 (partner and team) | `QE_TIER1_PASSWORD` (secret) | without a password tier 1 stays shut on every instance; the app asks for it, API calls send it in the header `x-tier1-password` |
| Tier 2 (team) | `QE_TEAM_PASSWORD` (secret) | without a password there is no team access; log in via the **Audit** button |
| Team session | `QE_SESSION_SECRET` (secret, `openssl rand -hex 32`) | signed cookie for 12 h; with a fixed key logins survive restarts |
| Shield the team instance | ingress behind VPN/SSO (recommended) | the team instance holds all data and the write routes; when public, only the passwords and the failed-attempt brake protect them |
| Port 9090 (exports, metrics) | `networkPolicy.enabled` (on in `values-team.yaml`) | only Quellenpanel pods and monitoring reach it; never publish it |
| Team login from another site | `QE_ALLOWED_ORIGINS` | only for embedded team views, HTTPS only |

Changing passwords: update the secret and restart the pods. A new `QE_SESSION_SECRET` logs out all
team sessions. Failed password attempts (login and headers) are throttled per address.

## Editing area (corrections)

The editing area exists on the **team instance** only:

1. Open the team instance (internal, e.g. `http://127.0.0.1:8082` with Compose).
2. Choose **Audit** at the top right and enter the team password (`QE_TEAM_PASSWORD`).
3. The view bar now shows **Korrekturen** (corrections).

There the team maintains the corrections (table with search, create, edit, delete, history with
initials), imports lists from CSV, JSON or XLSX with a preview and replaces the crawler table. A
source's profile additionally offers **Auf Blacklist** and **Beschreibung ergänzen**. After every
change the team recomputes the data; partner and public pick it up on their next sync (default
every 10 minutes). **Daten aktualisieren** in the Audit tier re-fetches the data from the
repository. Files and backups: [`docs/betrieb.md`](docs/betrieb.md#korrekturen-und-crawler-tabelle-team-bereich).

## Data via the API

All read endpoints return JSON without login (tier 0). The cleanest source is the public instance;
it only knows public fields. The full description is at `/openapi.json` (interactive at `/docs`).

```bash
H=https://quellen.example.org

# list with filters and paging (page 1, 50 entries, mathematics, OER only, most contents first)
curl "$H/api/sources?subject=Mathematik&oer=true&page=1&page_size=50&sort=contentCount&order=desc"

# search, educational level, crawlers only, at least 10 contents
curl "$H/api/sources?q=physik&level=Sekundarstufe%20I&crawler=true&min_count=10"

# one source (id from the list, e.g. crawler:bpb_spider)
curl "$H/api/sources/crawler:bpb_spider"

# example contents of a source, live from the repository
curl "$H/api/sources/crawler:bpb_spider/contents?max_items=12&skip=0"

# key figure (number of sources and contents) and filter values
curl "$H/api/kennzahl?subject=Biologie"
curl "$H/api/meta/filters"

# statistics (subjects, educational levels, content types)
curl "$H/api/stats"

# flat export as JSON or CSV (tier 1 and up: partner with password)
curl -H "x-tier1-password: $PW" "$H/api/export.csv?tier=1&subject=Chemie"
```

Fields of a source in the list: `id`, `name`, `contentCount`, `url`, `searchUrl` (link into the
search), `bezugsquelle`, `description`, `subjects`, `educationalContext`, `contentTypes`, `license`,
`oer`, `language`, `previewUrl`, `erschliessungsstatus`, `quality` (costs, ads, login, data
protection …). The list response has `total`, `page`, `pageSize`, `pages` and `items`.

Notes: at most 200 entries per page. Exports (`/api/export.json`, `/api/export.csv`) take the same
filters as the list. The live call `/contents` is throttled per client (429 with `Retry-After`).
Errors always look like `{"error", "message", "status", "trace_id"}`.

All endpoints:

```
GET  /api/sources · /api/sources/{id} · /api/sources/{id}/contents · /api/kennzahl
GET  /api/meta/filters · /api/stats · /api/capabilities · /api/health
GET  /api/export.json · /api/export.csv                        tier 1 and up
POST /api/sources/batch                                         several sources at once
GET  /api/stats/team · /api/protokoll.md|.json|.csv              team
POST /api/auth · /api/logout · GET /api/auth/status              team login
POST /jobs/refresh · GET /jobs/latest                            data refresh (team)
GET|POST /api/team/korrekturen · PUT|DELETE /api/team/korrekturen/{id}   corrections (team)
GET  /embed/{name} · /widgets/…                                  widgets
```

## Embedding (widgets)

One small script provides the source list, top 10 per subject, key figure, single source and
statistics, plus tiles and the whole app. Slim on a white page, without header, footer and frame:

```html
<script src="https://quellen.example.org/widgets/quellenpanel-widgets.js" defer></script>
<wlo-quellen-kacheln kopf="aus" fuss="aus" rahmen="aus" hintergrund="#ffffff"></wlo-quellen-kacheln>
<wlo-quellen-kacheln ansicht="liste" kopf="aus" fuss="aus" filter="aus" rahmen="aus" fach="Chemie"></wlo-quellen-kacheln>
<wlo-quellen-top fach="Biologie" max="10" farbe="#003b7c"></wlo-quellen-top>
```

The attribute names are German (`kopf` = header, `fuss` = footer, `rahmen` = frame, `ansicht` =
view, `hintergrund` = background, `farbe` = colour; `aus` = off). The same works as an iframe
(`/embed/quellen-kacheln?kopf=aus&fuss=aus&rahmen=aus`) or as a link to the app
(`/?kopf=aus&ansicht=liste`). All elements, attributes and colours: [`docs/widgets.md`](docs/widgets.md)
(German); test pages under `/widgets/beispiele/`.

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `QE_ROLE` | `team` | `team`, `partner` or `public` |
| `QE_TEAM_PASSWORD` | empty (no team access) | tier 2 password |
| `QE_TIER1_PASSWORD` | empty (tier 1 shut) | tier 1 password |
| `QE_SESSION_SECRET` | `session.key` in the data folder | key of the team session |
| `QE_EXPORT_SOURCE`, `QE_EXPORT_POLL_MINUTES` | empty, `10` | partner/public: export source with `{tier}`, sync interval in minutes |
| `QE_SEED_URL` | empty | team: starting data for the first start |
| `QE_AUTO_REFRESH_HOUR` | empty (off) | team: hour of the nightly refresh |
| `QE_ALLOWED_ORIGINS` | empty | origins allowed a team login from embedded pages |
| `QE_FRAME_ANCESTORS` | `*` (team: `'self'`) | who may embed the iframe widgets |
| `QE_THUMB_CACHE_MB` | `16` | preview image cache in MiB (`0` = off) |
| `QE_REPO_URL`, `QE_SEARCH_URL` | from the profile | repository and search |
| `QE_PROFILE`, `QE_PROFILES_DIR` | `wlo`, `profiles/` | repository profile |
| `QE_DATA_DIR` | `backend/data` (image: `/data`) | data directory |
| `TRUST_PROXY` | off | client address from `X-Forwarded-For` (only behind your own proxy) |
| `LOG_FORMAT`, `LOG_LEVEL` | `json`, `INFO` | logs |
| `QE_PORT`, `QE_INTERNAL_PORT`, `QE_HOST` | `8080`, `9090`, `0.0.0.0` | ports, bind address |

Complete with roles and secrets: [`docs/betrieb.md`](docs/betrieb.md#secrets-und-umgebung). Another
repository gets its own profile under `profiles/<name>/` ([`profiles/README.md`](profiles/README.md)).

## Development and tests

```bash
python -m ruff check .                         # lint (repo root)
cd backend && python -m pytest -q              # backend
cd frontend && npm test -- --watch=false       # frontend (vitest)
cd frontend && npm run lint:design             # design rules (edu-sharing)
```

Layout: `backend/` (FastAPI, data preparation, roles and tiers), `frontend/` (Angular 22, Material,
widgets), `profiles/` (repository profiles), `deploy/` (Compose, Helm, measurement), `docs/`. How
the data is built: [`docs/datenaufbereitung.md`](docs/datenaufbereitung.md). CI
(`.github/workflows/ci.yml`) additionally runs `pip-audit`, `npm audit`, Helm, kubeconform, alert
rules and the version check.
