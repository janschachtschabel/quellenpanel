"""Etappe 3 / Task 6: hardened image and the three-service compose reference."""
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_dockerfile_hardened():
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert text.count("@sha256:") == 2
    assert "EXPOSE 8080 9090" in text
    assert 'CMD ["python", "serve.py"]' in text
    assert "--port 8080" not in text
    assert "QE_DATA_DIR=/data" in text
    assert "127.0.0.1:9090/health" in text


def _compose(name):
    return yaml.safe_load((ROOT / "deploy" / name).read_text(encoding="utf-8"))["services"]


def test_compose_three_services_read_only():
    svc = _compose("docker-compose.yml")
    assert {"team", "partner", "public"} <= set(svc)
    for name in ("team", "partner", "public"):
        s = svc[name]
        assert s["read_only"] is True, name
        assert "/tmp" in s["tmpfs"], name
        assert str(s["user"]) == "10001", name
    assert "quellenpanel-data:/data" in svc["team"]["volumes"]
    assert all(p.startswith("127.0.0.1:") for p in svc["team"].get("ports", []))
    env = "\n".join(svc["partner"]["environment"])
    assert "QE_ROLE=partner" in env and "http://team:9090/internal/exports/stufe{tier}.json" in env
    assert "QE_ROLE=public" in "\n".join(svc["public"]["environment"])


def test_tls_compose_trusts_caddy():
    svc = _compose("docker-compose.tls.yml")
    assert {"team", "partner", "public", "caddy"} <= set(svc)
    for name in ("partner", "public"):
        assert "TRUST_PROXY=1" in "\n".join(svc[name]["environment"])
        assert "ports" not in svc[name]
        assert svc[name]["read_only"] is True
    caddy = (ROOT / "deploy" / "Caddyfile").read_text(encoding="utf-8")
    assert "public:8080" in caddy and "partner:8080" in caddy
    assert "9090" not in caddy
