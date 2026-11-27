"""Etappe 3 / Task 7: static checks of the Helm chart (no helm binary needed)."""
import json
import re
from pathlib import Path

import yaml

import config

ROOT = Path(__file__).resolve().parents[2]
CHART = ROOT / "deploy" / "helm" / "quellenpanel"


def test_chart_identity_and_version():
    chart = yaml.safe_load((CHART / "Chart.yaml").read_text(encoding="utf-8"))
    assert chart["name"] == "quellenpanel"
    assert chart["version"] == chart["appVersion"] == config.VERSION
    pkg = json.loads((ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert pkg["version"] == config.VERSION


def _params(text: str) -> set[str]:
    return set(re.findall(r"^\s*## @param ([\w.\-/]+)", text, re.M))


def test_every_value_documented():
    text = (CHART / "values.yaml").read_text(encoding="utf-8")
    params = _params(text)
    values = yaml.safe_load(text)
    missing = []
    for k, v in values.items():
        if isinstance(v, dict) and v:
            for k2 in v:
                key = f"{k}.{k2}"
                if key not in params and not any(p.startswith(key + ".") for p in params):
                    missing.append(key)
        elif k not in params:
            missing.append(k)
    assert not missing, missing


def test_config_has_all_env_values():
    cfg = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))["config"]
    for key in ("role", "profile", "tier1Password", "teamPassword", "sessionSecret", "existingSecret",
                "exportSource", "exportPollMinutes", "seedUrl", "autoRefreshHour", "allowedOrigins",
                "trustProxy", "repoUrl", "searchUrl"):
        assert key in cfg, key
    log = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))["log"]
    assert {"format", "level"} <= set(log)


def test_role_values_files():
    for role in ("public", "partner", "team"):
        v = yaml.safe_load((CHART / f"values-{role}.yaml").read_text(encoding="utf-8"))
        assert v["config"]["role"] == role


def test_templates_hardened_and_two_ports():
    dep = (CHART / "templates" / "deployment.yaml").read_text(encoding="utf-8")
    assert "readOnlyRootFilesystem: true" in dep
    assert "containerPort: 9090" in dep and "containerPort: 8080" in dep
    assert re.search(r'eq \.Values\.config\.role "team".*?Recreate', dep, re.S)
    for probe, path in (("livenessProbe", "/health"), ("startupProbe", "/health")):
        assert re.search(probe + r":\s*\n\s*httpGet:\s*\n\s*path: " + re.escape(path) + r"\s*\n\s*port: internal", dep), probe
    assert "seccompProfile" in dep and "RuntimeDefault" in dep
    for name in ("pvc.yaml", "networkpolicy.yaml", "servicemonitor.yaml", "prometheusrule.yaml"):
        assert (CHART / "templates" / name).is_file(), name
    svc = (CHART / "templates" / "service.yaml").read_text(encoding="utf-8")
    assert "-internal" in svc and "9090" in svc


def test_alert_rules_present():
    rules = (CHART / "templates" / "prometheusrule.yaml").read_text(encoding="utf-8")
    for alert in ("QuellenpanelRebuildStale", "QuellenpanelHigh5xx", "QuellenpanelExportFetchFailing"):
        assert alert in rules
    assert (CHART / "tests" / "rules-test.yaml").is_file()


def test_readiness_has_no_dependencies_and_checks_public_listener():
    # Leitfaden: readiness without dependencies (never /ready), on the public port, so a pod with a
    # broken API listener leaves the rotation while a pod without data still answers 503 + Retry-After.
    dep = (CHART / "templates" / "deployment.yaml").read_text(encoding="utf-8")
    assert re.search(r'readinessProbe:\s*\n\s*httpGet:\s*\n\s*path: /api/health\s*\n\s*port: http', dep)
    assert "/ready" not in dep


def test_clean_shutdown_prestop_and_grace():
    import serve
    dep = (CHART / "templates" / "deployment.yaml").read_text(encoding="utf-8")
    v = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))
    assert "preStop" in dep and "preStopSleepSeconds" in dep
    assert v["terminationGracePeriod"] > v["preStopSleepSeconds"] + serve.GRACEFUL_SECONDS


def test_no_data_alert():
    rules = (CHART / "templates" / "prometheusrule.yaml").read_text(encoding="utf-8")
    assert "QuellenpanelNoData" in rules
    assert "QuellenpanelNoData" in (CHART / "tests" / "rules.yaml").read_text(encoding="utf-8")
    assert "QuellenpanelNoData" in (CHART / "tests" / "rules-test.yaml").read_text(encoding="utf-8")


def test_team_ingress_allows_uploads():
    """Etappe 4: Uploads bis 5 MB (Crawler-Tabelle, Import) müssen durch das Team-Ingress passen."""
    v = yaml.safe_load((CHART / "values-team.yaml").read_text(encoding="utf-8"))
    size = v["ingress"]["annotations"]["nginx.ingress.kubernetes.io/proxy-body-size"]
    assert size.endswith("m") and int(size[:-1]) >= 6


def test_values_resources_match_messung():
    """Etappe 7: Requests/Limits je Rolle stehen so in docs/messung.md (Abschnitt Empfehlung)."""
    import re
    text = (ROOT / "docs/messung.md").read_text(encoding="utf-8")
    teil = text.split("## Empfehlung", 1)[1]
    for rolle in ("team", "partner", "public"):
        v = yaml.safe_load((CHART / f"values-{rolle}.yaml").read_text(encoding="utf-8"))["resources"]
        zeile = re.search(rf"^\|\s*{rolle}\s*\|([^\n]+)$", teil, re.M)
        assert zeile, rolle
        zellen = [z.strip().strip("`") for z in zeile.group(1).split("|")[:4]]
        assert zellen == [str(v["requests"]["cpu"]), str(v["requests"]["memory"]),
                          str(v["limits"]["cpu"]), str(v["limits"]["memory"])], rolle


def test_networkpolicy_restricts_egress_and_optionally_ingress_source():
    # Leitfaden: Netzwerkpartner benennen und Verkehr in beide Richtungen begrenzen.
    np = (CHART / "templates" / "networkpolicy.yaml").read_text(encoding="utf-8")
    assert "- Egress" in np
    assert "port: 53" in np and "port: 443" in np                      # DNS, repository/vocabs over HTTPS
    assert 'ne .Values.config.role "team"' in np and "port: 9090" in np  # partner/public → team exports
    assert "ingressNamespace" in np and "extraEgress" in np
    v = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))["networkPolicy"]
    assert v["ingressNamespace"] == "" and v["extraEgress"] == []
    for role in ("team", "partner", "public"):
        rv = yaml.safe_load((CHART / f"values-{role}.yaml").read_text(encoding="utf-8"))
        assert rv["networkPolicy"]["enabled"] is True, role


def test_configmap_sets_thumb_cache_and_frame_ancestors():
    cm = (CHART / "templates" / "configmap-env.yaml").read_text(encoding="utf-8")
    assert "QE_THUMB_CACHE_MB: {{ .Values.config.thumbCacheMB | quote }}" in cm
    assert "QE_FRAME_ANCESTORS: {{ .Values.config.frameAncestors | quote }}" in cm
    v = yaml.safe_load((CHART / "values.yaml").read_text(encoding="utf-8"))["config"]
    assert v["thumbCacheMB"] == 16 and v["frameAncestors"] == ""
