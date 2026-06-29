"""The tier-gated stats / export / protocol / multi-PDF / refresh routes: correct payload per
tier and correct gating (no end-user access to team-only or data-work routes)."""


def test_stats_overview_is_tiered(client, team_pw):
    t0 = client.get("/api/stats").json()
    assert "totalContents" in t0 and "topByContent" in t0      # end-user shape
    assert "topLanguages" in t0                                # languages moved into the base view
    assert "contentBrackets" not in t0                         # "content per source" chart removed
    assert "quellenverwaltung" not in t0                       # no extended data leaks in
    t1 = client.get("/api/stats?tier=1").json()
    assert "quellenverwaltung" in t1                           # extended (full) shape
    # Descriptive-metadata fill over Quelldatensätze, split into two balanced charts.
    bf = t1["beschreibendeFelder"]
    assert bf["basis"] >= 0 and bf["inhalt"] and bf["einordnung"]
    assert all(0 <= row["prozent"] <= 100 for row in bf["inhalt"] + bf["einordnung"])
    # The OVERVIEW is the full shape at tier 2 too — the problem data is a separate endpoint.
    t2 = client.get("/api/stats?tier=2", headers={"X-Team-Password": team_pw}).json()
    assert t2 == t1


def test_team_stats_separate_and_gated(client, team_pw):
    # The data-problem addendum lives behind a team-only endpoint (fail-closed).
    assert client.get("/api/stats/team").status_code == 403
    team = client.get("/api/stats/team", headers={"X-Team-Password": team_pw}).json()
    assert "probleme" in team and "feldFuellstand" in team
    assert "problemBeispiele" in team                          # per-flag example drill-down
    assert "feldHerkunft" not in team                          # replaced by the merge-flow diagram
    assert "metadaten" not in team["feldFuellstand"]           # metadata fill moved to tier 1


def test_export_requires_tier1(client):
    assert client.get("/api/export.json").status_code == 403          # tier 0 default
    assert client.get("/api/export.csv").status_code == 403
    ok = client.get("/api/export.json?tier=1")
    assert ok.status_code == 200 and isinstance(ok.json(), list) and ok.json()


def test_export_respects_filter(client):
    # The export honours the same filters as the list (so the file matches what is on screen).
    full = client.get("/api/export.json?tier=1").json()
    none = client.get("/api/export.json?tier=1&min_count=99999999").json()
    assert len(full) > 0 and len(none) == 0


def test_sources_tier2_has_hidden_breakdown(client, team_pw):
    d = client.get("/api/sources?tier=2&page_size=3", headers={"X-Team-Password": team_pw}).json()
    assert "hidden" in d and d["hidden"]["total"] == d["hidden"]["blacklist"] + d["hidden"]["mehrfach"]
    assert "hidden" not in client.get("/api/sources?page_size=3").json()   # tier 0 must not get it


def test_sources_lrt_filter_narrows_list(client):
    # The content-type (lrt) filter scopes the list: a non-matching value yields nothing, a real
    # one (from the filter vocabulary) yields a non-empty subset of the unfiltered total.
    base = client.get("/api/sources", params={"tier": 1, "page_size": 1}).json()["total"]
    assert base > 0
    assert client.get("/api/sources", params={"tier": 1, "lrt": "__no_such_type__"}).json()["total"] == 0
    lrts = client.get("/api/meta/filters").json().get("lrts") or []
    if lrts:
        sub = client.get("/api/sources", params={"tier": 1, "lrt": lrts[0], "page_size": 1}).json()["total"]
        assert 0 < sub <= base


def test_hidden_breakdown_respects_lrt_filter(client, team_pw):
    # Regression: the team hidden breakdown must be scoped to the SAME filter as the list. With a
    # content-type filter that matches nothing the list is empty, so nothing can be hidden in that
    # scope either — previously the re-run ignored lrt and reported the global hidden count.
    d = client.get("/api/sources", params={"tier": 2, "lrt": "__no_such_type__", "page_size": 3},
                   headers={"X-Team-Password": team_pw}).json()
    assert d["total"] == 0
    assert d["hidden"]["total"] == 0


def test_protokoll_team_only(client, team_pw):
    assert client.get("/api/protokoll.md").status_code == 403
    r = client.get("/api/protokoll.md", headers={"X-Team-Password": team_pw})
    assert r.status_code == 200 and r.text.strip()


def test_batch_is_tiered(client, team_pw):
    sid = client.get("/api/sources?page_size=1").json()["items"][0]["id"]
    pub = client.post("/api/sources/batch", json={"ids": [sid]}).json()["items"]
    assert pub and "internal" not in pub[0]                                  # tier 0 default
    team = client.post("/api/sources/batch?tier=2", json={"ids": [sid]},
                       headers={"X-Team-Password": team_pw}).json()["items"]
    assert team and "internal" in team[0]                                    # tier 2 with team


def test_thumb_rejects_foreign_host(client):
    assert client.get("/api/thumb?url=https://evil.example/x.jpg").status_code == 400


def test_refresh_team_only(client):
    assert client.post("/jobs/refresh").status_code == 403
    assert client.get("/jobs/latest").status_code == 200      # status is public


def test_cors_public_wildcard_for_any_origin(client):
    # Public data is readable from ANY origin, without credentials (wildcard CORS).
    r = client.get("/api/health", headers={"Origin": "https://random.example"})
    assert r.headers.get("access-control-allow-origin") == "*"
    assert "access-control-allow-credentials" not in r.headers


def test_cors_credentialed_grant_only_for_trusted_origin(client, monkeypatch):
    import config
    monkeypatch.setattr(config, "ALLOWED_ORIGINS", ["https://trusted.example"])
    # A trusted origin gets an origin-specific, credentialed grant (so the team cookie may flow).
    ok = client.get("/api/health", headers={"Origin": "https://trusted.example"})
    assert ok.headers.get("access-control-allow-origin") == "https://trusted.example"
    assert ok.headers.get("access-control-allow-credentials") == "true"
    # Any other origin still only gets the public wildcard (no credentials).
    other = client.get("/api/health", headers={"Origin": "https://other.example"})
    assert other.headers.get("access-control-allow-origin") == "*"
    assert "access-control-allow-credentials" not in other.headers
    # Preflight is answered by the middleware (the API declares no OPTIONS routes).
    pre = client.options("/api/auth", headers={"Origin": "https://trusted.example"})
    assert pre.status_code == 204
    assert pre.headers.get("access-control-allow-origin") == "https://trusted.example"
    assert pre.headers.get("access-control-allow-credentials") == "true"
    assert "POST" in pre.headers.get("access-control-allow-methods", "")


def test_login_cookie_is_cross_site_for_trusted_origin(client, team_pw, monkeypatch):
    import config
    monkeypatch.setattr(config, "ALLOWED_ORIGINS", ["https://trusted.example"])
    r = client.post("/api/auth", headers={"X-Team-Password": team_pw, "Origin": "https://trusted.example"})
    assert r.status_code == 200
    cookie = r.headers.get("set-cookie", "").lower()
    assert "samesite=none" in cookie and "secure" in cookie       # sendable cross-site
    # A same-origin login (no trusted Origin) stays locked down to SameSite=strict.
    same = client.post("/api/auth", headers={"X-Team-Password": team_pw})
    assert "samesite=strict" in same.headers.get("set-cookie", "").lower()
