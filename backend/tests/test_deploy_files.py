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


def test_root_compose_ist_aktuelle_team_entwicklungsinstanz():
    svc = yaml.safe_load((ROOT / "docker-compose.build.yml").read_text(encoding="utf-8"))["services"]["quellenpanel"]
    env = svc["environment"]
    assert env["QE_ROLE"] == "team" and "QE_SESSION_SECRET" in env
    assert "QE_PUBLIC_ONLY" not in env
    assert any(v.endswith(":/data") for v in svc["volumes"])
    assert all(p.startswith("127.0.0.1:") for p in svc["ports"])
    assert "9090/health" in " ".join(svc["healthcheck"]["test"])
    assert svc["read_only"] is True and str(svc["user"]) == "10001"


def test_gitlab_versionspruefung_bricht_wirklich_ab():
    # set -e stops on neither part of an && list: every check needs its own line or an explicit exit.
    import yaml as _yaml
    gl = _yaml.safe_load((ROOT / ".gitlab-ci.yml").read_text(encoding="utf-8"))
    for line in gl["version check"]["script"]:
        if line.startswith("test ") or " && test " in line:
            assert "&&" not in line or line.rstrip().endswith("exit 1"), line


# --- Server behind an existing Traefik proxy: docker-compose.yml in the repository root -----------
def _server():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    return text, yaml.safe_load(text)


def test_server_compose_deploys_without_any_variable():
    text, doc = _server()
    assert ":?" not in text and "\t" not in text and "<<:" not in text and "*common" not in text
    variables = [part.split("}")[0] for part in text.split("${")[1:]]
    assert variables and all(":-" in v and "${" not in v for v in variables), variables   # all with default
    assert doc["networks"]["default"]["name"] == "${TRAEFIK_NETWORK:-quellenpanel-web}"
    assert not any(n.get("external") for n in doc["networks"].values())


def test_server_compose_one_instance_by_default():
    _, doc = _server()
    svc = doc["services"]
    assert set(svc) == {"team", "partner", "public"}
    # A deploy always pulls the image CI built from main (no local build that a host may skip or
    # cache): every deploy runs the latest main, QE_IMAGE pins a version.
    assert "build" not in svc["team"]
    # One port serves every tier; tier 1 and 2 need their passwords (fail-closed).
    assert svc["team"]["ports"] == ["${BIND:-0.0.0.0}:${PORT:-18080}:8080"]
    assert "deploy" not in svc["team"]
    # Separate instances are optional: off unless SEPARATE_INSTANCES=1, so equal ports never clash.
    for name in ("partner", "public"):
        assert svc[name]["deploy"]["replicas"] == "${SEPARATE_INSTANCES:-0}", name
        assert svc[name]["environment"]["QE_EXPORT_SOURCE"] == "http://team:9090/internal/exports/stufe{tier}.json"
    assert svc["partner"]["ports"] == ["${PARTNER_PORT:-18081}:8080"]
    assert svc["public"]["ports"] == ["${PUBLIC_PORT:-18082}:8080"]
    for name, host in (("team", "DOMAIN"), ("partner", "PARTNER_DOMAIN"), ("public", "PUBLIC_DOMAIN")):
        s = svc[name]
        assert all(":80:" not in p and ":443:" not in p for p in s["ports"]), name   # 80/443: proxy
        assert all("9090" not in p for p in s["ports"]), name                       # metrics stay inside
        assert s["image"] == "${QE_IMAGE:-ghcr.io/janschachtschabel/quellenpanel:main}", name
        assert s["pull_policy"] == "always", name
        assert s["read_only"] is True and str(s["user"]) == "10001", name
        assert s["environment"]["TRUST_PROXY"] == "1", name
        labels = "\n".join(s["labels"])
        assert f"quellenpanel-{name}.rule=Host(`${{{host}:-}}`)" in labels, name
        assert "loadbalancer.server.port=8080" in labels and "traefik.docker.network=" in labels, name
    team = svc["team"]["environment"]
    assert team["QE_ROLE"] == "team" and "quellenpanel-data:/data" in svc["team"]["volumes"]
    assert team["QE_TEAM_PASSWORD"] == "${QE_TEAM_PASSWORD:-}"
    assert team["QE_TIER1_PASSWORD"] == "${QE_TIER1_PASSWORD:-}"
    assert team["QE_SEED_URL"].endswith("/profiles/wlo/daten}")   # never a deploy without corrections


def test_server_env_example_starts_empty():
    lines = [ln for ln in (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
             if ln.strip() and not ln.startswith("#")]
    assert lines and all(ln.endswith("=") for ln in lines), lines
    text, _ = _server()
    for ln in lines:
        assert "${" + ln[:-1] + ":-" in text, ln


def test_seed_copies_exist_where_the_compose_points():
    for name in ("korrekturen.csv", "crawler.csv"):
        assert (ROOT / "profiles" / "wlo" / "daten" / name).is_file()


def test_release_workflow_nur_von_hand_und_prueft_version():
    import yaml as _yaml
    doc = _yaml.safe_load((ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8"))
    on = doc.get(True, doc.get("on"))        # PyYAML reads the key `on` as True
    assert set(on) == {"workflow_dispatch"}
    assert doc["permissions"] == {"contents": "read"}
    job = doc["jobs"]["release"]
    assert job["permissions"]["contents"] == "write"
    run = " ".join(s.get("run", "") for s in job["steps"])
    assert "pyproject.toml" in run and "refs/heads/main" in run and "gh release create" in run


def test_github_veroeffentlicht_image_fuer_compose_mit_revision():
    import yaml as _yaml
    doc = _yaml.safe_load((ROOT / ".github/workflows/docker-publish.yml").read_text(encoding="utf-8"))
    assert doc["permissions"] == {"contents": "read"}
    job = doc["jobs"]["ghcr"]
    assert job["permissions"]["packages"] == "write"
    text = (ROOT / ".github/workflows/docker-publish.yml").read_text(encoding="utf-8")
    assert "ghcr.io/${{ github.repository }}" in text
    assert "QE_REVISION=${{ github.sha }}" in text
    assert "ARG QE_REVISION" in (ROOT / "Dockerfile").read_text(encoding="utf-8")
