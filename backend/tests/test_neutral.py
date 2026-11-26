"""Der Kern enthält keine WLO-Spezifika mehr; die stehen im Profil (profiles/wlo/)."""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
FORBIDDEN = ("ccm:oeh_", "wirlernenonline", "mds_oeh", "openeduhub")


def test_core_has_no_wlo_specifics():
    files = list(BACKEND.glob("*.py")) + list((BACKEND / "tools").glob("*.py"))
    hits = [(p.name, s) for p in files for s in FORBIDDEN if s in p.read_text(encoding="utf-8").lower()]
    assert hits == []
