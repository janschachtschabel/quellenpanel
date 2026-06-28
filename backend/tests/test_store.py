"""The Bezugsquelle-family grouping (publisher + its sub-channels) behind the detail view's
"related sources" — e.g. all YouTube channels group under the parent "YouTube"."""
import store


def _r(rid, name, bq, flags=(), cc=0, node=""):
    return {"id": rid, "name": name, "contentCount": cc,
            "identity": {"bezugsquelle": bq, "nodeId": node}, "flags": list(flags)}


def test_family_key_groups_subchannels_under_parent():
    parent = _r("bq:youtube", "YouTube", "YouTube", cc=50000)
    child1 = _r("bq:yt-a", "YouTube - Mathe", "YouTube - Mathe", ["BQ_SUBCHANNEL"])
    child2 = _r("node:b", "YouTube - Physik", "YouTube - Physik", ["BQ_SUBCHANNEL"], node="n9")
    other = _r("bq:serlo", "Serlo", "Serlo", cc=10)
    assert store._family_key(parent) == store._family_key(child1) == store._family_key(child2)
    assert store._family_key(other) != store._family_key(parent)
    # a hyphenated name WITHOUT the BQ_SUBCHANNEL flag is not split (its own family)
    assert store._family_key(_r("x", "VCI Nord / Youtube", "VCI Nord / Youtube")) != store._family_key(parent)


def test_related_sources_returns_family_siblings():
    parent = _r("bq:youtube", "YouTube", "YouTube", cc=50000)
    child1 = _r("bq:yt-a", "YouTube - Mathe", "YouTube - Mathe", ["BQ_SUBCHANNEL"], cc=5)
    child2 = _r("node:b", "YouTube - Physik", "YouTube - Physik", ["BQ_SUBCHANNEL"], cc=3, node="n9")
    saved = store._DATA["byFamily"]
    try:
        idx = {}
        for r in (parent, child1, child2):
            idx.setdefault(store._family_key(r), []).append(r)
        store._DATA["byFamily"] = idx
        rel = store.related_sources(child1)
        assert rel["bezugsquelle"] == "YouTube"            # parent label, not the sub-channel name
        assert rel["count"] == 2                            # parent + the other child
        names = [i["name"] for i in rel["items"]]
        assert "YouTube" in names and "YouTube - Physik" in names
        assert rel["items"][0]["name"] == "YouTube"         # sorted by content desc
        # a source with no siblings → None (no empty section in the UI)
        assert store.related_sources(_r("bq:lonely", "Lonely", "Lonely")) is None
        # family_count: the cheap card-badge count excludes self, 0 when alone / no Bezugsquelle
        assert store.family_count(child1) == 2
        assert store.family_count(parent) == 2
        assert store.family_count(_r("bq:lonely", "Lonely", "Lonely")) == 0
        assert store.family_count(_r("x", "NoBq", "")) == 0
    finally:
        store._DATA["byFamily"] = saved
