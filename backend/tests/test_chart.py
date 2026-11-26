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


def test_team_readiness_keeps_pod_reachable_while_building():
    # A team without data must stay in its Service, or nobody can reach login/refresh/503 answer.
    dep = (CHART / "templates" / "deployment.yaml").read_text(encoding="utf-8")
    assert re.search(r'readinessProbe:\s*\n\s*httpGet:\s*\n\s*path: \{\{ if eq \$\.Values\.config\.role "team" \}\}/health'
                     r'\{\{ else \}\}/ready\{\{ end \}\}', dep)


def test_no_data_alert():
    rules = (CHART / "templates" / "prometheusrule.yaml").read_text(encoding="utf-8")
    assert "QuellenpanelNoData" in rules
    assert "QuellenpanelNoData" in (CHART / "tests" / "rules.yaml").read_text(encoding="utf-8")
    assert "QuellenpanelNoData" in (CHART / "tests" / "rules-test.yaml").read_text(encoding="utf-8")
