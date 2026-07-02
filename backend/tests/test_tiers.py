"""The tier model is the security spine of the merged app: tier 0 must never leak internal data,
tier resolution must cap unauthenticated callers, and QE_PUBLIC_ONLY must hard-cap everyone."""
import os
import subprocess
import sys
import types

import config
import filtering
import serialize
import session
import tiers

LEAK = ("internal", "flags", "provenance", "confidence", "hasInternal", "fieldGeneration", "bind",
        "ki", "binding", "familyCount", "related")


def _rec():
    """A record carrying internal fields + a hidden flag, to prove the gate strips them."""
    return {
        "id": "x", "name": "Serlo", "kind": "manuell", "contentCount": 5, "erschliessung": "",
        "identity": {"bezugsquelle": "Serlo", "nodeId": "n1", "spider": "serlo_spider"},
        "public": {"URL": "https://serlo.org", "Beschreibung": "d", "Faecher": ["Mathematik"],
                   "robots.txt": "erlaubt"},  # a KI/legal field → tier-1 "KI-Nutzung & Recht" section
        "internal": {"Node-ID": "n1", "Erschliessungsstatus (genau)": "9."},
        "provenance": {"URL": "WLO-API", "Faecher": "WLO-API (Facette)", "robots.txt": "datencrawler.csv"},
        "confidence": "high",
        "flags": ["BLACKLIST", "WLO_MIGRATION"], "quality": {"Kosten": "nein"},
        "fieldGeneration": [], "fieldActiveCount": 0,
    }


def test_tier0_strips_all_internal():
    t0 = serialize.source(_rec(), 0, detail=True)
    assert not [k for k in LEAK if k in t0]
    assert t0["searchUrl"].startswith("https://suche.wirlernenonline.de/")


def test_tier1_detail_has_ki_fields_but_no_internal():
    t1 = serialize.source(_rec(), 1, detail=True)
    assert t1["ki"].get("robots.txt") == "erlaubt"  # AI-usage / legal fields surfaced
    assert "fieldGeneration" in t1
    assert t1["binding"] == {"node": "n1", "spider": "serlo_spider"}  # public identity, from tier 1
    assert "internal" not in t1
    assert "provenance" not in t1  # per-field data source is team-only (tier 2)


def test_family_link_is_team_only():
    """The Bezugsquelle family (familyCount badge / related list) is Audit-tier only (tier 2): it is
    data-work context, stripped below that. count is card-only, related detail-only (even at tier 2)."""
    rel = {"bezugsquelle": "YouTube", "count": 2,
           "items": [{"id": "a", "name": "YouTube - Mathe", "contentCount": 0, "hasNode": False}]}
    # tier 0/1: neither the count nor the related list is exposed
    assert "familyCount" not in serialize.source(_rec(), 0, family=3)
    assert "familyCount" not in serialize.source(_rec(), 1, family=3)
    assert "related" not in serialize.source(_rec(), 1, detail=True, related=rel)
    # tier 2: card carries the count, detail the related list
    assert serialize.source(_rec(), 2, family=3)["familyCount"] == 3
    assert serialize.source(_rec(), 2, detail=True, related=rel)["related"]["bezugsquelle"] == "YouTube"
    assert "related" not in serialize.source(_rec(), 2, family=3)                      # related is detail-only
    assert "familyCount" not in serialize.source(_rec(), 2, detail=True, related=rel)  # count is card-only


def test_tier0_shows_coarse_status_tier2_exact():
    """Tier 0/1 see only the coarse public cataloguing statement; the exact internal status code is
    re-attached at tier 2 (team) — the raw editorial code never leaks to end users."""
    assert serialize.source(_rec(), 0, detail=True)["erschliessungsstatus"] == "im Bestand verfuegbar"
    t2 = serialize.source(_rec(), 2, detail=True)
    assert t2["erschliessungsstatus"] == "9."
    assert t2["internal"]["Erschliessungsstatus (genau)"] == "9."


def test_tier1_list_stays_light():
    t1 = serialize.source(_rec(), 1)  # list (detail=False)
    assert "provenance" not in t1 and "internal" not in t1 and "bind" not in t1


def test_tier1_list_has_field_active_count():
    t1 = serialize.source(_rec(), 1)
    assert "fieldActiveCount" in t1 and t1["fieldActiveCount"] == 0


def test_only_field_profile_filter():
    with_profile = {**_rec(), "fieldGeneration": [{"field": "x", "aktiv": True}], "fieldActiveCount": 1}
    without_profile = {**_rec(), "fieldGeneration": [], "fieldActiveCount": 0}
    all_recs = [with_profile, without_profile]
    assert filtering.filter_records(all_recs, None, None, None, None, None, 0, None, True,
                                    show_blacklist=True) == [with_profile]
    assert filtering.filter_records(all_recs, None, None, None, None, None, 0, None, False,
                                    show_blacklist=True) == all_recs


def test_tier2_detail_exposes_internal_and_all_flags():
    t2 = serialize.source(_rec(), 2, detail=True)
    assert "internal" in t2 and "BLACKLIST" in t2["flags"]


def test_tier2_detail_has_mapped_provenance():
    t2 = serialize.source(_rec(), 2, detail=True)
    # provenance is keyed by the flat field names the detail view renders + the KI field names.
    assert t2["provenance"].get("subjects") == "WLO-API (Facette)"   # Faecher → subjects
    assert t2["provenance"].get("robots.txt") == "datencrawler.csv"  # KI key keeps its name


def test_tier2_list_has_flags_and_bind_not_internal():
    t2 = serialize.source(_rec(), 2)  # team list: flags + source-binding badges, no internal bulk
    assert "flags" in t2 and "internal" not in t2
    assert t2["bind"] == {"node": "n1", "bezugsquelle": "Serlo", "spider": "serlo_spider"}


def _req(cookie=None):
    return types.SimpleNamespace(cookies=({session.COOKIE: cookie} if cookie else {}))


def test_max_tier_tier1_open_by_default():
    assert tiers.max_tier(_req(), None, None, None) == 1  # tier 1 open, no team pw


def test_max_tier_team_password():
    assert tiers.max_tier(_req(), "test-team-pw", None, None) == 2


def test_check_tier1_open_when_unset():
    assert config.check_tier1_pw(None, None) is True  # open unless QE_TIER1_PASSWORD set


def test_api_sources_default_is_tier0_clean(client):
    d = client.get("/api/sources?page_size=3").json()
    assert d["tier"] == 0 and d["items"]
    for it in d["items"]:
        assert not [k for k in LEAK if k in it]


def test_api_tier2_capped_without_auth(client):
    # Tier 1 is open by default, so an unauthenticated caller asking for tier 2 is capped to
    # tier 1 (the highest it may reach) — and crucially still carries no internal data.
    d = client.get("/api/sources?tier=2&page_size=3").json()
    assert d["tier"] == 1
    assert all("internal" not in it for it in d["items"])


def test_api_tier2_list_has_flags_not_internal(client, team_pw):
    d = client.get("/api/sources?tier=2&page_size=5", headers={"X-Team-Password": team_pw}).json()
    assert d["tier"] == 2 and d["items"]
    assert all("flags" in it for it in d["items"])          # team list carries flags
    assert all("bind" in it for it in d["items"])           # + source-binding badges
    assert all("internal" not in it for it in d["items"])   # internal is detail-only


def test_api_detail_tier1_no_internal(client):
    sid = client.get("/api/sources?page_size=1").json()["items"][0]["id"]
    d = client.get(f"/api/sources/{sid}?tier=1").json()
    assert "ki" in d and "fieldGeneration" in d and "internal" not in d and "provenance" not in d


def test_api_detail_tier2_has_internal(client, team_pw):
    sid = client.get("/api/sources?page_size=1").json()["items"][0]["id"]
    d = client.get(f"/api/sources/{sid}?tier=2", headers={"X-Team-Password": team_pw}).json()
    assert "internal" in d and "flags" in d and "provenance" in d


def test_capabilities_reflect_auth(client, team_pw):
    base = client.get("/api/capabilities").json()
    assert base["maxTier"] == 1 and base["teamAvailable"] is True and base["publicOnly"] is False
    withpw = client.get("/api/capabilities", headers={"X-Team-Password": team_pw}).json()
    assert withpw["maxTier"] == 2


def test_health_and_unknown_404(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/api/sources/does-not-exist").status_code == 404


def test_public_only_hard_caps_even_team():
    """QE_PUBLIC_ONLY=1 must serve tier 0 even with the correct team password (verified in a
    fresh process, since the flag is read at import time)."""
    env = {**os.environ, "QE_PUBLIC_ONLY": "1", "QE_TEAM_PASSWORD": "test-team-pw"}
    code = (
        "from fastapi.testclient import TestClient; import app, config;"
        "assert config.PUBLIC_ONLY;"
        "import contextlib;"
        "c=TestClient(app.app);"
        "c.__enter__();"
        "d=c.get('/api/sources?tier=2&page_size=3', headers={'X-Team-Password':'test-team-pw'}).json();"
        "assert d['tier']==0, d['tier'];"
        "assert all('internal' not in it for it in d['items']);"
        "assert c.get('/api/capabilities').json()['maxTier']==0;"
        "print('ok')"
    )
    r = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True,
                       cwd=os.path.dirname(os.path.abspath(config.__file__)))
    assert r.returncode == 0, r.stderr
    assert "ok" in r.stdout
