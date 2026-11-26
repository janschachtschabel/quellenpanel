"""Migration der alten Korrekturdateien (Korrekturliste + Supplements) ins Langformat."""
import csv
import json
import subprocess
import sys
from pathlib import Path

from korrekturen import KorrekturSet, load_korrekturen
from tools.migrate_korrekturen import migrate

FIX = Path(__file__).parent / "fixtures" / "golden"
REPO = Path(__file__).resolve().parents[2]
SHIFTED = ("blacklist", "whitelist")


def _old_loader(path):
    """Der Korrekturlisten-Loader aus truth_loaders, Stand vor Etappe 1 (Referenz)."""
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    sep = ";" if text.count(";") > text.count(",") else ","
    out = {}
    for r in csv.DictReader(text.splitlines(), delimiter=sep):
        nid = (r.get("Node-Id") or "").strip()
        if nid:
            out[nid] = {"liste": (r.get("Liste") or "").strip().lower(),
                        "bezugsquelle": (r.get("Bezugsquelle") or "").strip(),
                        "spider": (r.get("Spider") or "").strip()}
    return out


def _old_and_new(korr_csv, sup_json, monkeypatch):
    rows, bericht = migrate(korr_csv, sup_json, "2026-11-26")
    new = KorrekturSet(eintraege=rows).als_node_dict()
    return _old_loader(korr_csv), new, rows, bericht


def _assert_equivalent(old, new):
    assert set(new) == set(old)
    assert {k: v["liste"] for k, v in new.items()} == {k: v["liste"] for k, v in old.items()}
    for nid, o in old.items():
        assert new[nid]["bezugsquelle"] == o["bezugsquelle"]
        if o["spider"] not in SHIFTED:          # verrutschte Zeilen: Spider-Wert ist kein Spider
            assert new[nid]["spider"] == o["spider"]


def test_migration_equals_old_loader(monkeypatch):
    old, new, rows, _ = _old_and_new(FIX / "alt/quellen_korrektur.csv", FIX / "alt/source_supplements.json", monkeypatch)
    _assert_equivalent(old, new)
    sup = json.loads((FIX / "alt/source_supplements.json").read_text(encoding="utf-8"))
    sup.pop("_provenance", None)
    expected = {k: {kk: vv for kk, vv in v.items() if vv} for k, v in sup.items()}
    assert KorrekturSet(eintraege=rows).supplements() == expected


def test_shifted_row_is_reported(monkeypatch):
    _, _, rows, bericht = _old_and_new(FIX / "alt/quellen_korrektur.csv", FIX / "alt/source_supplements.json", monkeypatch)
    assert any("verschoben" in r.kommentar for r in rows)
    assert any("verschoben" in b for b in bericht)


def test_mojibake_title_is_repaired(monkeypatch):
    _, _, rows, _ = _old_and_new(FIX / "alt/quellen_korrektur.csv", FIX / "alt/source_supplements.json", monkeypatch)
    assert any(r.kommentar.startswith("Arbeitsblatt über Brüche") for r in rows)


def test_cli_writes_loadable_file(tmp_path):
    out = tmp_path / "k.csv"
    subprocess.run([sys.executable, "-m", "tools.migrate_korrekturen", str(FIX / "alt/quellen_korrektur.csv"),
                    str(FIX / "alt/source_supplements.json"), str(out), "--bericht", str(tmp_path / "b.md")],
                   cwd=REPO / "backend", check=True)
    s = load_korrekturen(out)
    assert s.fehler == [] and s.eintraege
    assert (tmp_path / "b.md").read_text(encoding="utf-8").startswith("# Migrationsbericht")


def test_real_wlo_korrekturen_are_valid():
    s = load_korrekturen(REPO / "profiles/wlo/daten/korrekturen.csv")
    assert s.fehler == []
    assert len(s.als_node_dict()) == 440
    assert len(s.supplements()) == 36           # Einträge der bisherigen source_supplements.json
