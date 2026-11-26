"""Korrekturen im Langformat: Lesen, Schreiben, Excel-Varianten, Fehler, Widersprüche."""
from korrekturen import Korrektur as K
from korrekturen import KorrekturSet, load_korrekturen, write_korrekturen

NID = "4c1df1cc-2d5a-4f55-aeac-039630326b99"
HEAD = "Typ;Schlüssel;Aktion;Wert;Kommentar;Geändert von;Geändert am"


def _write(path, lines, sep=";", bom=True, eol="\r\n"):
    text = eol.join(line.replace(";", sep) for line in lines) + eol
    path.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
    return path


def test_roundtrip(tmp_path):
    rows = [K("node", NID, "blacklist", "", "Titel X", "jan", "2026-11-26"),
            K("bezugsquelle", "YouTube", "beschreibung", "Videos; mit Semikolon", "", "", "")]
    write_korrekturen(tmp_path / "k.csv", rows)
    raw = (tmp_path / "k.csv").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert "Typ;Schlüssel;Aktion".encode() in raw
    assert b"\r\n" in raw
    assert load_korrekturen(tmp_path / "k.csv").eintraege == rows


def test_excel_variants(tmp_path):
    a = _write(tmp_path / "a.csv", [HEAD + ";;", f"node;{NID};whitelist;;;;;;"])
    b = _write(tmp_path / "b.csv", [HEAD, f"node;{NID};whitelist;;;;"], sep=",", bom=False, eol="\n")
    for p in (a, b):
        s = load_korrekturen(p)
        assert [e.aktion for e in s.eintraege] == ["whitelist"]
        assert s.fehler == []


def test_invalid_rows_are_reported(tmp_path):
    p = _write(tmp_path / "k.csv", [HEAD, f"node;{NID};löschen;;;;", "node;abc;blacklist;;;;", "node;;blacklist;;;;"])
    s = load_korrekturen(p)
    assert s.eintraege == []
    assert [m.zeile for m in s.fehler] == [2, 3, 4]


def test_contradiction_last_wins_with_warning(tmp_path):
    p = _write(tmp_path / "k.csv", [HEAD, f"node;{NID};whitelist;;;;", f"node;{NID};blacklist;;;;"])
    s = load_korrekturen(p)
    assert s.als_node_dict()[NID]["liste"] == "blacklist"
    assert len(s.warnungen) == 1 and NID in s.warnungen[0].text


def test_vermerk_creates_empty_list_entry(tmp_path):
    s = load_korrekturen(_write(tmp_path / "k.csv", [HEAD, f"node;{NID};vermerk;;;;"]))
    assert s.als_node_dict() == {NID: {"liste": "", "bezugsquelle": "", "spider": ""}}


def test_overrides_fill_node_dict(tmp_path):
    s = load_korrekturen(_write(tmp_path / "k.csv", [
        HEAD, f"node;{NID};whitelist;;;;", f"node;{NID};bezugsquelle_setzen;ZUM;;;", f"node;{NID};spider_setzen;zum_spider;;;"]))
    assert s.als_node_dict()[NID] == {"liste": "whitelist", "bezugsquelle": "ZUM", "spider": "zum_spider"}


def test_supplements_lowercase_keys(tmp_path):
    s = load_korrekturen(_write(tmp_path / "k.csv", [
        HEAD, "bezugsquelle;YouTube;beschreibung;Videos;;;", "bezugsquelle;YouTube;vorschaubild;https://x/p.png;;;"]))
    assert s.supplements() == {"youtube": {"description": "Videos", "previewUrl": "https://x/p.png"}}


def test_missing_file_is_empty(tmp_path):
    for s in (load_korrekturen(tmp_path / "fehlt.csv"), load_korrekturen(None)):
        assert s.eintraege == [] and s.fehler == [] and s.warnungen == []
    assert KorrekturSet(eintraege=[], fehler=[], warnungen=[]).als_node_dict() == {}
