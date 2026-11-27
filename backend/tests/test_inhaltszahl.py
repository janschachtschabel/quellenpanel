"""Inhaltszahl und Suchlink passen zur WLO-Suche (Filter »Quelle« = Bezugsquelle)."""
import urllib.parse

import enduser
import truth


def test_crawler_takes_larger_bezugsquelle_count():
    # bpb: the Spider delivered 62867, the WLO search shows 63034 under the Bezugsquelle
    n, src = truth.crawler_content("bpb_spider", "bpb", {"bpb_spider": 62867}, {"bpb": 63034})
    assert (n, src) == (63034, "bezugsquelle")


def test_crawler_spanning_several_publishers_keeps_spider_count():
    n, src = truth.crawler_content("agg_spider", "A", {"agg_spider": 900}, {"A": 300})
    assert (n, src) == (900, "spider")


def test_dead_crawler_stays_zero_without_bezugsquelle():
    assert truth.crawler_content("dead", "", {"dead": 0}, {"X": 5}) == (0, "spider")


def test_crawler_without_spider_uses_bezugsquelle():
    assert truth.crawler_content("", "B", {}, {"B": 7}) == (7, "bezugsquelle")


def _flt(url):
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)["filters"][0]
    return q


def test_search_link_filters_by_bezugsquelle_not_title():
    r = {"name": "Ecole Science bei YouTube", "identity": {"bezugsquelle": "Ecole Science"}}
    assert _flt(enduser.record_search_url(r)) == '{"source":["Ecole Science"]}'


def test_search_link_falls_back_to_name():
    r = {"name": "Nur Titel", "identity": {"bezugsquelle": ""}}
    assert _flt(enduser.record_search_url(r)) == '{"source":["Nur Titel"]}'
