# Helm chart `quellenpanel`

One chart, one release per role. All three releases can share a namespace; resource names are
`quellenpanel-<role>`.

```bash
# 1. Team (tier 2, data owner): one replica, Recreate, PVC at /data
helm upgrade --install quellenpanel-team deploy/helm/quellenpanel \
  -f deploy/helm/quellenpanel/values-team.yaml --set config.existingSecret=quellenpanel-team-secrets

# 2. Partner (tier 1, password) and 3. public (tier 0): fetch their export from the team
helm upgrade --install quellenpanel-partner deploy/helm/quellenpanel \
  -f deploy/helm/quellenpanel/values-partner.yaml --set config.existingSecret=quellenpanel-partner-secrets
helm upgrade --install quellenpanel-public deploy/helm/quellenpanel \
  -f deploy/helm/quellenpanel/values-public.yaml
```

The existing Secret holds the keys `QE_TEAM_PASSWORD`, `QE_TIER1_PASSWORD`, `QE_SESSION_SECRET`
(only those the role needs). Without `existingSecret` the chart creates one from `config.*Password`
and `config.sessionSecret`.

## What the chart sets up

- **Two ports:** `http` 8080 (Service `quellenpanel-<role>`, behind the ingress) and `internal` 9090
  (Service `quellenpanel-<role>-internal`, never behind an ingress): `/health` (liveness and startup
  probe; readiness for the team, so its single pod stays reachable while it builds), `/ready`
  (readiness for partner/public), `/metrics`, `/internal/exports/…` (team only).
- **Restricted security context:** non-root uid 10001, read-only root filesystem, no privilege
  escalation, all capabilities dropped, seccomp `RuntimeDefault`. Writes go to `/tmp` (emptyDir) and
  `/data` (PVC for the team, emptyDir otherwise).
- **Team:** `replicas: 1`, `strategy: Recreate`, PVC `quellenpanel-team-data` (kept on uninstall).
  First start with an empty volume seeds from `config.seedUrl` or builds from the live repository;
  until then `/ready` is 503 and the API answers 503 "Daten werden aufgebaut".
- **Partner/public:** `replicaCount` replicas, `config.exportSource` (default: the team's internal
  Service). They keep serving the last valid export if the team is unreachable.
- **`config.trustProxy`** (default on): the client IP for the rate limits is the rightmost
  `X-Forwarded-For` entry. Keep it only behind an ingress that overwrites the header
  (ingress-nginx does by default, `use-forwarded-headers: false`).
- **Optional:** `networkPolicy.enabled` (9090 only from quellenpanel pods and the monitoring
  namespace), `metrics.serviceMonitor.enabled`, `metrics.prometheusRule.enabled` with the alerts
  `QuellenpanelRebuildStale` (team data older than 26 h), `QuellenpanelNoData` (no data for 6 h), `QuellenpanelHigh5xx` (more than 5 % 5xx
  over 10 min) and `QuellenpanelExportFetchFailing` (partner/public: only failed fetches for 30 min).

## Checks

```bash
helm lint --strict deploy/helm/quellenpanel -f deploy/helm/quellenpanel/values-team.yaml
helm template t deploy/helm/quellenpanel -f deploy/helm/quellenpanel/values-team.yaml | kubeconform -strict -ignore-missing-schemas
promtool test rules deploy/helm/quellenpanel/tests/rules-test.yaml
```

`tests/rules.yaml` is a static rendering of `templates/prometheusrule.yaml`; keep both in sync. All
values are documented with `## @param` in `values.yaml`.
