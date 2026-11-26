"""Crawler-Tabelle hochladen: Pflichtspalten, Auswirkungen, Ersetzen mit Sicherung."""
import pytest

import anwenden
import crawler_upload as cu
import korrektur_store as ks
import repo_profile

HEAD = "Titel;Crawler (Spider);Quelldatensatz (Prod);Bezugsquelle\n"


def _csv(rows, head=HEAD):
    return ("﻿" + head + "".join(rows)).encode("utf-8")


@pytest.fixture
def daten(tmp_path, monkeypatch):
    monkeypatch.setenv("QE_DATA_DIR", str(tmp_path))
    repo_profile.reset()
    (tmp_path / "crawler.csv").write_bytes(_csv(["A;spider_a;;Quelle A\n", "B;spider_b;;Quelle B\n"]))
    calls = []
    monkeypatch.setattr(anwenden, "nach_aenderung",
                        lambda: calls.append(1) or {"neuBerechnet": False, "wirktBeimNaechstenAufbau": True})
    yield tmp_path, calls
    repo_profile.reset()


def test_missing_required_column(daten):
    r = cu.pruefen(_csv(["A;spider_a\n"], head="Titel;Spider\n"))
    assert r["ok"] is False
    assert "Crawler (Spider)" in r["fehlendePflicht"]


def test_spider_diff(daten):
    r = cu.pruefen(_csv(["A;spider_a;;Quelle A\n", "B neu;spider_b;;Quelle B\n", "C;spider_c;;C\n"]))
    assert r["ok"] is True and r["zeilen"] == 3
    assert r["spider"] == {"neu": ["spider_c"], "entfallen": [], "geaendert": ["spider_b"], "gleich": 1}


def test_spider_dropped(daten):
    r = cu.pruefen(_csv(["A;spider_a;;Quelle A\n"]))
    assert r["spider"]["entfallen"] == ["spider_b"]


def test_unreadable_upload(daten):
    with pytest.raises(cu.UploadFehler):
        cu.pruefen(b"")


def test_ersetzen_backs_up_writes_and_applies(daten):
    tmp, calls = daten
    alt = (tmp / "crawler.csv").read_bytes()
    neu = _csv(["A;spider_a;;Quelle A\n"])
    res = cu.ersetzen(neu, "JS")
    assert (tmp / "crawler.csv").read_bytes() == neu
    backups = list(tmp.glob("crawler-2*.csv"))
    assert len(backups) == 1 and backups[0].read_bytes() == alt
    assert calls == [1] and res["anwenden"]["wirktBeimNaechstenAufbau"] is True
    h = ks.verlauf()[0]
    assert h["vorgang"] == "crawler_ersetzen" and h["wer"] == "JS"
    assert h["alt"] == "2 Zeilen" and h["neu"] == "1 Zeilen"


def test_ersetzen_refuses_invalid(daten):
    tmp, calls = daten
    alt = (tmp / "crawler.csv").read_bytes()
    with pytest.raises(cu.UploadFehler):
        cu.ersetzen(_csv(["A;x\n"], head="Titel;Spider\n"), "JS")
    assert (tmp / "crawler.csv").read_bytes() == alt and calls == []


def test_cp1252_upload_keeps_umlaut_columns(daten):
    """Review-Befund: Excel-CSV (cp1252) wird als UTF-8 gespeichert, Spalten mit Umlaut bleiben lesbar."""
    import truth_loaders
    tmp, _ = daten
    data = ("Titel;Crawler (Spider);Quelldatensatz (Prod);Häufigkeit\nA;spider_a;;wöchentlich\n").encode("cp1252")
    cu.ersetzen(data, "JS")
    prof = truth_loaders.load_crawler_profiles()["spider_a"]
    assert "wöchentlich" in str(prof)
