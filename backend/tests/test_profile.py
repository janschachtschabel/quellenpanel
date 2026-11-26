"""Profil-Lader: WLO-Werte, Fehlermeldungen, Env-Auswahl, Bezug zur field_policy."""
import shutil
from pathlib import Path

import pytest

import field_policy as fp
import repo_profile

PROFILES = Path(__file__).resolve().parents[2] / "profiles"


def test_wlo_profile_values():
    p = repo_profile.load_profile("wlo", PROFILES)
    assert p.repo_url == "https://redaktion.openeduhub.net"
    assert p.felder["publisher"] == "ccm:oeh_publisher_combined"
    assert len(p.qualitaet) == 18
    assert p.qualitaet[0] == ("Sachrichtigkeit", "ccm:oeh_quality_correctness_DISPLAYNAME")
    assert p.ignore_spiders == frozenset({"wirlernenonline_spider"})
    assert p.publiziert_wf == ("150_PUBLISH_IN_SEARCH", "155_ELEMENT_UNLOCK_BUFFET")
    assert p.daten_dir == PROFILES / "wlo" / "daten"


def test_unknown_profile_names_path(tmp_path):
    with pytest.raises(repo_profile.ProfileError, match=str(tmp_path / "gibtsnicht")):
        repo_profile.load_profile("gibtsnicht", tmp_path)


def test_missing_required_feld_is_named(tmp_path):
    (tmp_path / "kaputt").mkdir()
    text = (PROFILES / "wlo" / "profil.toml").read_text(encoding="utf-8")
    text = text.replace('publisher = "ccm:oeh_publisher_combined"\n', "")
    (tmp_path / "kaputt" / "profil.toml").write_text(text, encoding="utf-8")
    with pytest.raises(repo_profile.ProfileError, match="publisher"):
        repo_profile.load_profile("kaputt", tmp_path)


def test_get_reads_env(monkeypatch, tmp_path):
    shutil.copytree(PROFILES / "wlo", tmp_path / "anders", ignore=shutil.ignore_patterns("daten"))
    monkeypatch.setenv("QE_PROFILES_DIR", str(tmp_path))
    monkeypatch.setenv("QE_PROFILE", "anders")
    repo_profile.reset()
    try:
        assert repo_profile.get().root == tmp_path / "anders"
    finally:
        repo_profile.reset()


def test_crawler_keys_are_in_field_policy():
    p = repo_profile.load_profile("wlo", PROFILES)
    known = set(fp.CRAWLER_PUBLIC_KEYS) | set(fp.CRAWLER_INTERNAL_KEYS)
    assert set(p.crawler_spalten.values()) <= known
