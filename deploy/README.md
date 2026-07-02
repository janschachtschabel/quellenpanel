# Deploying WLO Quellenpanel

One image serves the 3-tier API **and** the built Angular SPA. All access tiers are configured via
env (all optional; unset ⇒ end-user-only, fail-closed) — see the table in the top-level
[`README.md`](../README.md#deployment).

## Docker Compose (HTTP)

```bash
cp deploy/.env.example deploy/.env      # set IMAGE, PORT, and any QE_* you need
docker compose -f deploy/docker-compose.yml up -d
# → http://localhost:${PORT:-8080}
```

## Docker Compose with automatic HTTPS (Caddy + nip.io/sslip.io)

No own domain needed — Caddy fetches a Let's Encrypt cert for `SITE_ADDRESS`
(`<label>.<YOUR-SERVER-IP>.nip.io`, the IP keeps its dots).

```bash
cp deploy/.env.example deploy/.env      # set IMAGE and SITE_ADDRESS (+ QE_* as needed)
docker compose -f deploy/docker-compose.tls.yml up -d
# → https://<SITE_ADDRESS>
```

This variant runs uvicorn with `--forwarded-allow-ips` and Caddy overwrites `X-Forwarded-For` with
the real client IP (`deploy/Caddyfile`), so the app's per-client rate limits (login brute-force
guard, thumbnail/contents throttle) key on the true client — not the proxy address. **Do not** copy
that flag into a setup where the app port is published directly (a client could then spoof the IP).

## Kubernetes (Helm)

Chart: [`helm/quellenpanel`](helm/quellenpanel) — single-replica `Deployment` (stateless: bundled
`data/truth.json`, no PVC), ConfigMap + Secret for the `QE_*` env, Service + Ingress.

```bash
helm upgrade --install quellenpanel deploy/helm/quellenpanel \
  --namespace quellenpanel --create-namespace \
  --set image.name=<registry>/projects/wlo/quellenpanel --set image.tag=main \
  --set ingress.hosts[0]=quellenpanel.example.de \
  --set config.teamPassword='<team-password>'
```

Details + all values in [`helm/quellenpanel/README.md`](helm/quellenpanel/README.md). The GitLab CI
(`.gitlab-ci.yml`) packages and pushes this chart on tags/branches when `HELM_REGISTRY` is set.

## Notes

- **Single instance:** the team session store and the in-process rate limits are per-process. Run
  one replica (Compose = one container; Helm `replicaCount: 1`). A horizontally scaled deployment
  would split them → flaky team login.
- **Data refresh:** `QE_AUTO_REFRESH_HOUR` (and the manual "Daten aktualisieren" button in the Audit
  tier) rebuild the snapshot from the live WLO API into the container filesystem — ephemeral, reverts
  to the bundled snapshot on restart. To ship updated data permanently, rebuild the image.
