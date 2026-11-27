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


def test_image_builds_and_ships_widgets():
    """Etappe 5: Das Image baut das Widget-Skript und das Element-Bundle und liefert beide aus."""
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "npm run build:widgets" in text and "npm run build:element" in text
    assert "/build/dist-widgets /app/quellenpanel/frontend/dist-widgets" in text
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "build:widgets" in ci and "build:element" in ci


def test_element_bundle_styles_never_touch_host_page():
    """Review-Befund Etappe 5: Das eingebettete App-Bundle darf html/body/:root der Gastseite nicht stylen."""
    import json
    import re
    ang = json.loads((ROOT / "frontend/angular.json").read_text(encoding="utf-8"))
    el = ang["projects"]["quellenliste-x"]["architect"]["build"]["configurations"]["element"]
    styles = el["styles"]
    assert "src/styles.element.scss" in styles and "src/styles.scss" not in styles
    text = (ROOT / "frontend/src/styles.element.scss").read_text(encoding="utf-8")
    code = re.sub(r"//[^\n]*", "", text)
    assert not re.search(r"(^|[\s,}])(html|body|:root)\s*[,{]", code)


def test_element_bundle_resets_inherited_host_typography():
    """Probe Etappe 5: kursive/fette Gast-Schrift darf nicht in die Kacheln erben."""
    text = (ROOT / "frontend/src/styles.element.scss").read_text(encoding="utf-8")
    for regel in ("font-style: normal", "font-weight: 400", "line-height: normal"):
        assert regel in text
