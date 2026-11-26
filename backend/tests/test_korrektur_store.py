"""Korrektur-Store: Datei im Datenverzeichnis, Version, Verlauf, Sicherung."""
import csv
import io

import pytest

import korrektur_store as ks
from korrekturen import Korrektur, write_korrekturen

NODE = "27c77a87-8250-4a26-9d95-3b24cd162539"


@pytest.fixture
def daten(tmp_path, monkeypatch):
    monkeypatch.setenv("QE_DATA_DIR", str(tmp_path))
    return tmp_path


def _verlauf(daten):
    text = (daten / "korrekturen-verlauf.csv").read_bytes().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(text), delimiter=";"))


def test_without_data_file_reads_profile_start(daten):
    stand = ks.lesen()
    assert len(stand["eintraege"]) > 100
    assert len(stand["version"]) == 16
    assert stand["eintraege"][0]["id"] == 0
    assert not (daten / "korrekturen.csv").exists()


def test_anlegen_writes_data_dir_and_history(daten):
    v = ks.lesen()["version"]
    n = len(ks.lesen()["eintraege"])
    neu = ks.anlegen({"typ": "node", "schluessel": NODE, "aktion": "whitelist", "wert": "",
                      "kommentar": "Test"}, "JS", v)
    assert len(neu["eintraege"]) == n + 1
    last = neu["eintraege"][-1]
    assert last["aktion"] == "whitelist" and last["geaendert_von"] == "JS" and last["geaendert_am"]
    assert (daten / "korrekturen.csv").is_file()
    h = _verlauf(daten)
    assert h[-1]["Vorgang"] == "anlegen" and h[-1]["Wer"] == "JS" and h[-1]["Alt"] == ""
    assert NODE in h[-1]["Neu"]


def test_aendern_and_loeschen(daten):
    stand = ks.anlegen({"typ": "node", "schluessel": NODE, "aktion": "whitelist"}, "JS", ks.lesen()["version"])
    i = stand["eintraege"][-1]["id"]
    stand = ks.aendern(i, {"typ": "node", "schluessel": NODE, "aktion": "blacklist"}, "AB", stand["version"])
    assert stand["eintraege"][i]["aktion"] == "blacklist"
    n = len(stand["eintraege"])
    stand = ks.loeschen(i, "AB", stand["version"])
    assert len(stand["eintraege"]) == n - 1
    h = _verlauf(daten)
    assert [r["Vorgang"] for r in h[-2:]] == ["aendern", "loeschen"]
    assert "whitelist" in h[-2]["Alt"] and "blacklist" in h[-2]["Neu"]
    assert "blacklist" in h[-1]["Alt"] and h[-1]["Neu"] == ""


def test_unknown_id_is_rejected(daten):
    v = ks.lesen()["version"]
    with pytest.raises(ks.UngueltigeKorrektur):
        ks.loeschen(99999, "JS", v)


@pytest.mark.parametrize("k", [
    {"typ": "node", "schluessel": "keine-uuid", "aktion": "blacklist"},
    {"typ": "node", "schluessel": NODE, "aktion": "gibtsnicht"},
    {"typ": "bezugsquelle", "schluessel": "x", "aktion": "blacklist"},
])
def test_invalid_row_is_rejected_and_file_unchanged(daten, k):
    v = ks.lesen()["version"]
    with pytest.raises(ks.UngueltigeKorrektur):
        ks.anlegen(k, "JS", v)
    assert not (daten / "korrekturen.csv").exists()


def test_wrong_version_conflicts(daten):
    with pytest.raises(ks.VersionKonflikt):
        ks.anlegen({"typ": "node", "schluessel": NODE, "aktion": "blacklist"}, "JS", "0" * 16)
    assert not (daten / "korrekturen.csv").exists()


@pytest.mark.parametrize("wer", ["", "   ", "x" * 41])
def test_wer_is_required_and_short(daten, wer):
    with pytest.raises(ks.UngueltigeKorrektur):
        ks.anlegen({"typ": "node", "schluessel": NODE, "aktion": "blacklist"}, wer, ks.lesen()["version"])


def test_ersetzen_alle_makes_dated_backup(daten):
    write_korrekturen(daten / "korrekturen.csv", [Korrektur("node", NODE, "whitelist")])
    alt = (daten / "korrekturen.csv").read_bytes()
    stand = ks.ersetzen_alle([Korrektur("node", NODE, "blacklist")], "JS", ks.lesen()["version"],
                             "import_ersetzen", sicherung=True)
    assert [e["aktion"] for e in stand["eintraege"]] == ["blacklist"]
    backups = list(daten.glob("korrekturen-2*.csv"))
    assert len(backups) == 1 and backups[0].read_bytes() == alt
    assert _verlauf(daten)[-1]["Vorgang"] == "import_ersetzen"


def test_verlauf_newest_first(daten):
    v = ks.lesen()["version"]
    v = ks.anlegen({"typ": "node", "schluessel": NODE, "aktion": "whitelist"}, "A", v)["version"]
    ks.anlegen({"typ": "node", "schluessel": NODE, "aktion": "blacklist"}, "B", v)
    h = ks.verlauf()
    assert [e["wer"] for e in h[:2]] == ["B", "A"]
    assert set(h[0]) == {"zeitpunkt", "wer", "vorgang", "alt", "neu"}
