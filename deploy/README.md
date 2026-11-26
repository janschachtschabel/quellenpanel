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
