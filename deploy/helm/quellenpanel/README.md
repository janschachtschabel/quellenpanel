# quellenpanel — Helm chart

Deploys the WLO Quellenpanel (3-tier FastAPI API + embedded Angular SPA in one image) to Kubernetes.

The app is **stateless**: it serves the bundled `data/truth.json` snapshot from the image, so the
chart runs a plain single-replica `Deployment` with **no PersistentVolume**.

## Install

```bash
helm upgrade --install quellenpanel deploy/helm/quellenpanel \
  --namespace quellenpanel --create-namespace \
  --set image.name=docker.edu-sharing.com/projects/wlo/quellenpanel \
  --set image.tag=main \
  --set ingress.hosts[0]=quellenpanel.example.de \
  --set config.teamPassword='<team-password>'
```

## Key values

| Value | Default | Purpose |
|---|---|---|
| `replicaCount` | `1` | **Keep 1** — team session + rate-limit state is in-process (`backend/session.py`). |
| `service.port` | `8080` | Cluster-internal port; the container listens on 8080. |
| `config.publicOnly` | `false` | Hard-cap every request at tier 0 (public/embedded). |
| `config.teamPassword` | `""` | Enables tier 2 (Audit). Empty ⇒ team disabled (fail-closed). → Secret. |
| `config.tier1Password` | `""` | Optional gate for tier 1 (Details). Empty ⇒ open. → Secret. |
| `config.allowedOrigins` | `""` | Comma-separated origins for a credentialed cross-origin team login. |
| `config.autoRefreshHour` | `""` | Hour 0–23 for the optional nightly rebuild (see note). |
| `config.repoUrl` / `config.searchUrl` | prod | Point live queries + the search link at another repo. |
| `ingress.enabled` / `ingress.hosts` | `true` / nip.io | Ingress (nginx class by default). |

Passwords (`config.teamPassword`, `config.tier1Password`) land in the chart **Secret**; everything
else in the **ConfigMap**. `FORWARDED_ALLOW_IPS=*` is set so uvicorn trusts the ingress's
`X-Forwarded-For` (the pod is only reachable via the ingress) — the per-client rate limits then key
on the real client IP.

## Data refresh note

`config.autoRefreshHour` (and the manual "Daten aktualisieren" button in the Audit tier) rebuild the
snapshot from the live WLO API into the **container filesystem** — this is **ephemeral**: on pod
restart the app reverts to the image's bundled snapshot. That is fine as a "freshen" operation; to
ship updated data permanently, rebuild the image. (No PVC is provisioned; `readOnlyRootFilesystem`
is therefore left `false` so the refresh can write.)
