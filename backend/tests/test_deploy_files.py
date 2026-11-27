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


def test_ci_runs_design_lint():
    """Etappe 6: CI prüft die edu-sharing-Designregeln."""
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "lint:design" in ci


def test_primary_surfaces_use_readable_token():
    """Review-Befund Etappe 6: Flächen mit weißer Schrift nutzen --primaryText (bei jeder Markenfarbe lesbar)."""
    import re
    bad = []
    for f in (ROOT / "frontend/src/app").glob("*.component.ts"):
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            if re.search(r"background(-color)?:\s*var\(--(wlo-primary|primary)\)", line):
                bad.append(f"{f.name}:{i}")
    assert bad == []


# --- Abschlussreview Etappe 7: Release-Pipeline und Team-Isolation -----------------------------------

def test_gitlab_laedt_das_paket_mit_dem_chartnamen_hoch():
    import yaml as _yaml
    name = _yaml.safe_load((ROOT / "deploy/helm/quellenpanel/Chart.yaml").read_text(encoding="utf-8"))["name"]
    ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
    assert f"--upload-file {name}-${{CHART_VERSION}}.tgz" in ci


def test_gitlab_taggt_image_und_chart_ohne_v_wie_appversion():
    """Chart-Standard: Tag = appVersion (1.0.0). Der Git-Tag heißt v1.0.0 → das 'v' muss weg."""
    ci = (ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8")
    assert '${CI_COMMIT_TAG#v}' in ci
    assert 'CHART_VERSION="${CHART_VERSION#v}"' in ci


def test_github_veroeffentlicht_kein_latest():
    pub = (ROOT / ".github/workflows/docker-publish.yml").read_text(encoding="utf-8")
    assert "latest=false" in pub
    assert "tags `latest`" not in (ROOT / "README.md").read_text(encoding="utf-8")


def test_team_values_schalten_networkpolicy_ein():
    import yaml as _yaml
    v = _yaml.safe_load((ROOT / "deploy/helm/quellenpanel/values-team.yaml").read_text(encoding="utf-8"))
    assert v["networkPolicy"]["enabled"] is True


def test_uebergabe_nennt_team_isolation_als_betriebsschritt():
    text = (ROOT / "docs/uebergabe/README.md").read_text(encoding="utf-8")
    assert "VPN/SSO" in text and "networkPolicy.enabled" in text
    betrieb = (ROOT / "docs/betrieb.md").read_text(encoding="utf-8")
    assert "ohne `qe_role`" in betrieb.lower()


def test_gitlab_prueft_version_tag_und_chart_wie_github():
    import yaml as _yaml
    gl = _yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8"))
    script = "\n".join(gl["version check"]["script"])
    assert "pyproject.toml" in script and "Chart.yaml" in script and "package.json" in script
    assert "CI_COMMIT_TAG" in script                      # tag = "v" + version
    helm = gl["helm lint"]
    assert helm["image"]["name"] == "alpine/helm:3.19.0"
    assert all(f"values-{r}.yaml" in "\n".join(helm["script"]) for r in ("team", "partner", "public"))
    assert gl[".helm_base"]["image"]["name"] != "alpine/helm:latest"


def test_github_workflows_lesen_nur_und_dependabot_ist_an():
    import yaml as _yaml
    for wf in ("ci.yml", "docker-publish.yml"):
        doc = _yaml.safe_load((ROOT / ".github/workflows" / wf).read_text(encoding="utf-8"))
        assert doc.get("permissions") == {"contents": "read"}, wf
    dep = _yaml.safe_load((ROOT / ".github/dependabot.yml").read_text(encoding="utf-8"))
    ecos = {(u["package-ecosystem"], u["directory"]) for u in dep["updates"]}
    assert {("pip", "/backend"), ("npm", "/frontend"), ("github-actions", "/"), ("docker", "/")} <= ecos
