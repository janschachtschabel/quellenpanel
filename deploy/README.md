# Deploying WLO Quellenpanel

One image serves the API **and** the built Angular SPA. It runs as three instances, one per role
(`QE_ROLE`):

| Instance | Tier | Holds | Reachable |
|---|---|---|---|
| `team` | 2 (Audit) | the full data in `/data` (volume), builds the tier exports | internal only (VPN/SSO) |
| `partner` | 1 (Steckbrief, `QE_TIER1_PASSWORD`) | tier-0/1 exports, fetched from the team | partners |
| `public` | 0 (source list, widgets) | tier-0 export, fetched from the team | everyone |

Each container listens on **8080** (API + SPA) and **9090** (internal: `/health`, `/ready`,
`/metrics`, `/internal/exports/…`). Never publish 9090. The image carries no data: on first start
with an empty volume the team seeds from `QE_SEED_URL` or builds from the live repository. Until
then its API answers 503 "Daten werden aufgebaut" and `/ready` stays 503, while `/health` is 200.
Operations details are in [`docs/betrieb.md`](../docs/betrieb.md).

## Server with Traefik

For a Docker server that already runs Traefik on ports 80/443 (Let's Encrypt), for example a Docker
panel that deploys a compose file straight from a GitHub URL. The file is
[`docker-compose.yml`](../docker-compose.yml) in the repository root, with
[`.env.example`](../.env.example) as the starting `.env`.

1. Deploy `https://github.com/janschachtschabel/quellenpanel` (branch `main`). No variable is needed:
   the team builds the image from the repository (a few minutes), loads `korrekturen.csv` and
   `crawler.csv` from `profiles/wlo/daten` and then builds the data from the live repository (the pages
   answer 503 "Daten werden aufgebaut" meanwhile). Nothing is reachable from outside yet.
2. Edit `.env`: `DOMAIN` (public list, plain host name without `https://`), optionally
   `PARTNER_DOMAIN` with `QE_TIER1_PASSWORD`, and `QE_TEAM_PASSWORD`. Deploy again.
3. Point a DNS A record of each name to the server. Without an own domain,
   `quellen.<SERVER-IP>.sslip.io` works as well. Traefik fetches the certificates.

The team instance is not reachable while `TEAM_DOMAIN` is empty. Set it only for tests or behind
VPN/SSO, and always with a long `QE_TEAM_PASSWORD`. Without `QE_SESSION_SECRET` the team keeps a
random key in the data volume (`session.key`), so logins survive restarts.

Details: no ports are published (80/443 belong to Traefik); all three join the network
`TRAEFIK_NETWORK` (default `quellenpanel-web`, created if missing, never `external`); routers are named
`quellenpanel-public|partner|team`; entry point and resolver default to `websecure` and
`letsencrypt`. With exactly one proxy in front the apps run with `TRUST_PROXY=1`. Partner and public
fetch their exports from `http://team:9090` inside that network.

```bash
docker compose up -d --build              # update to the newest code of the branch in QE_GIT_URL
docker compose logs -f team               # rebuild progress; "Startdaten fehlen" = seed not loaded
docker compose restart team               # retry the seed after a network error
docker compose config -q && echo CONFIG-OK
```

For a fixed version set `QE_GIT_URL=https://github.com/janschachtschabel/quellenpanel.git#v1.0.0`.
`docker-compose.build.yml` is the local development variant (one team instance from the checkout).

## Docker Compose (HTTP)

```bash
cp deploy/.env.example deploy/.env      # set IMAGE, passwords, QE_SESSION_SECRET, QE_SEED_URL
docker compose -f deploy/docker-compose.yml up -d
# public  → http://localhost:${PORT:-8080}
# partner → http://localhost:${PARTNER_PORT:-8081}
# team    → http://127.0.0.1:${TEAM_PORT:-8082}  (this host only)
```

All three run `read_only` with a tmpfs `/tmp`, as uid 10001, without capabilities.

## Docker Compose with automatic HTTPS (Caddy + nip.io/sslip.io)

No own domain needed: Caddy fetches Let's Encrypt certificates for `SITE_ADDRESS` (public) and
`PARTNER_ADDRESS` (partner), e.g. `<label>.<YOUR-SERVER-IP>.nip.io` (the IP keeps its dots).

```bash
cp deploy/.env.example deploy/.env      # set IMAGE, SITE_ADDRESS, PARTNER_ADDRESS (+ QE_*)
docker compose -f deploy/docker-compose.tls.yml up -d
```

Caddy overwrites `X-Forwarded-For` with the real client IP (`deploy/Caddyfile`), and partner and
public run with `TRUST_PROXY=1`, so the per-client rate limits (tier-1 / login brute-force guard,
thumbnail and contents throttle) key on the true client. **Never** set `TRUST_PROXY` where the app
port is published directly, or behind a proxy that does not overwrite the header.

## Kubernetes (Helm)

Chart: [`helm/quellenpanel`](helm/quellenpanel), with one values file per role. Details and all
values in [`helm/quellenpanel/README.md`](helm/quellenpanel/README.md).

## Notes

- **Team = one replica.** The rebuild job, the logout revocation list and the in-process rate limits
  are per process. Team sessions themselves are signed (`QE_SESSION_SECRET`) and survive restarts.
- **Data refresh:** `QE_AUTO_REFRESH_HOUR` and the "Daten aktualisieren" button (Audit tier) rebuild
  the data into `/data`; partner and public pick up the new export within `QE_EXPORT_POLL_MINUTES`.
