"""Abfragen über den Export: gleiche Treffer und Reihenfolge wie die Datensatz-Abfrage (Etappe 2)."""
import pytest

import app
import exports
import export_query as eq
from test_exports import golden  # noqa: F401  (fixture: golden records + meta)
from test_golden import _reset_profile  # noqa: F401

BASE = {"q": "", "subject": "", "level": "", "erschliessung": "", "oer": None, "crawler": None,
        "min_count": 1, "flag": None, "show_blacklist": False, "sort": "contentCount", "order": "desc",
        "only_field_profile": False, "has_node": None, "has_bezugsquelle": None, "has_spider": None,
        "lrt": ""}


def _cases(doc):
    fl = doc["filters"]
    first = lambda key: (fl[key] or [""])[0]  # noqa: E731
    return [
        {}, {"has_node": True}, {"has_node": False}, {"has_bezugsquelle": True}, {"has_spider": True},
        {"crawler": True}, {"oer": True}, {"oer": False}, {"min_count": 0},
        {"sort": "name", "order": "asc"}, {"sort": "name", "order": "desc", "min_count": 0},
        {"subject": first("subjects")}, {"level": first("levels")}, {"lrt": first("lrts")},
        {"only_field_profile": True}, {"has_node": True, "min_count": 0},
    ]


@pytest.fixture
def setup(golden, monkeypatch):  # noqa: F811
    records, meta = golden
    monkeypatch.setitem(app._DATA, "records", records)
    return records, meta


@pytest.mark.parametrize("tier", [0, 1])
def test_equivalence_with_record_query(setup, tier):
    doc = exports.build_export(*setup, tier)
    for case in _cases(doc):
        f = {**BASE, **case}
        assert [e["id"] for e in eq.query(doc, f)] == [r["id"] for r in app._query_records(tier, **f)], case


def test_q_search_matches_name(setup):
    records, _ = setup
    doc = exports.build_export(*setup, 0)
    name = next(r["name"] for r in records if "BLACKLIST" not in r["flags"])
    f = {**BASE, "q": name[:5].upper(), "min_count": 0}
    assert [e["id"] for e in eq.query(doc, f)] == [r["id"] for r in app._query_records(0, **f)]


def test_zweit_only_in_node_view(setup):
    records, _ = setup
    doc = exports.build_export(*setup, 0)
    zweit = next(r["id"] for r in records if "ZWEITDATENSATZ" in r["flags"] and "BLACKLIST" not in r["flags"])
    assert zweit not in [e["id"] for e in eq.query(doc, {**BASE, "min_count": 0})]
    assert zweit in [e["id"] for e in eq.query(doc, {**BASE, "min_count": 0, "has_node": True})]


def test_team_filters_ignored(setup):
    doc = exports.build_export(*setup, 1)
    std = [e["id"] for e in eq.query(doc, BASE)]
    f = {**BASE, "flag": "BLACKLIST", "show_blacklist": True, "erschliessung": "9."}
    assert [e["id"] for e in eq.query(doc, f)] == std


def test_page_shape(setup):
    doc = exports.build_export(*setup, 0)
    p = eq.page(doc, {**BASE, "min_count": 0}, 2, 3)
    assert p["tier"] == 0 and p["page"] == 2 and p["pageSize"] == 3
    assert p["total"] == len(eq.query(doc, {**BASE, "min_count": 0}))
    assert p["pages"] == (p["total"] + 2) // 3
    assert len(p["items"]) == min(3, p["total"] - 3) and "hidden" not in p
    assert p["items"][0] == eq.query(doc, {**BASE, "min_count": 0})[3]["card"]


def test_detail_batch_rows_contents(setup):
    records, _ = setup
    doc = exports.build_export(*setup, 1)
    it = doc["items"][0]
    assert eq.detail(doc, it["id"]) == it["detail"]
    assert eq.detail(doc, "gibts:nicht") is None
    ids = [e["id"] for e in doc["items"]] * 60
    assert len(eq.batch(doc, ids[:150])) == 100
    assert eq.rows(doc, BASE) == [e["row"] for e in eq.query(doc, BASE)]
    assert eq.rows(exports.build_export(*setup, 0), BASE) == []
    crawler = next(r for r in records if r["kind"] == "crawler" and r["identity"].get("spider")
                   and "BLACKLIST" not in r["flags"])
    assert eq.contents_target(doc, crawler["id"]) == ("replication_source", crawler["identity"]["spider"])
    assert eq.contents_target(doc, "gibts:nicht") is None


def test_erschliessung_ignored_below_team_documented(setup):
    # Bewusste Abweichung: der genaue (interne) Statusfilter wirkt unter Stufe 2 nicht mehr.
    doc = exports.build_export(*setup, 0)
    std = [e["id"] for e in eq.query(doc, BASE)]
    assert [e["id"] for e in eq.query(doc, {**BASE, "erschliessung": "9."})] == std


def test_partial_filter_dict_defaults_min_count_1(setup):
    doc = exports.build_export(*setup, 0)
    assert [e["id"] for e in eq.query(doc, {})] == [r["id"] for r in app._query_records(0)]
