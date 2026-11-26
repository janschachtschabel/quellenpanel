"""repo_profile.py — the repository profile (everything repository-specific).

The generic core (fetch, merge, serve) knows no metadata-set details of a particular
edu-sharing instance. Property names, vocabulary URIs, special-case spiders, the column
layout of the crawler table and branding live in ``profiles/<id>/profil.toml``.

Named ``repo_profile`` (not ``profile``) so it never shadows the standard-library profiler.
Leaf module: imports nothing from the app, so config and every other module may import it.
"""
from __future__ import annotations

import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType

DEFAULT_PROFILES_DIR = Path(__file__).resolve().parent.parent / "profiles"

REQUIRED_FELDER: tuple[str, ...] = (
    "node_uuid", "title", "www_url", "description", "publisher", "license", "license_oer",
    "subjects", "subjects_entry", "educational_context", "lrt", "language", "language_fallback",
    "keywords", "author", "target_group", "language_level", "language_target", "curriculum",
    "fsk", "age_from", "age_to", "replication_source", "general_identifier",
    "editorial_status", "wf_status",
)
_REQUIRED_REPOSITORY = ("url", "search_url", "mds", "vocab_sources_url", "quelle_property", "quelle_werte")
_REQUIRED_SPIDER = ("kennung_enthaelt", "ignorieren", "migration", "migration_quelle",
                    "platzhalter_bezugsquellen", "lrt_quelle_stichwort", "publiziert_wf_status")
_REQUIRED_CRAWLER = ("spider_spalte", "quelldatensatz_spalte", "spalten")


class ProfileError(Exception):
    """A profile is missing or incomplete; the message names the file and the missing keys."""


@dataclass(frozen=True)
class Profile:
    id: str
    name: str
    root: Path
    repo_url: str
    search_url: str
    mds: str
    vocab_sources_url: str
    quelle_property: str
    quelle_werte: tuple[str, ...]
    felder: Mapping[str, str]
    qualitaet: tuple[tuple[str, str], ...]
    spider_kennung: str
    ignore_spiders: frozenset[str]
    migration_spiders: frozenset[str]
    migration_quelle: str
    platzhalter_bq: frozenset[str]
    lrt_quelle_stichwort: str
    publiziert_wf: tuple[str, ...]
    crawler_spalten: Mapping[str, str]
    crawler_spider_spalte: str
    crawler_quelldatensatz_spalte: str
    branding: Mapping[str, str]

    @property
    def daten_dir(self) -> Path:
        """Curated starting data of the profile (crawler table, corrections)."""
        return self.root / "daten"


def _require(section: dict, keys: tuple[str, ...], name: str, path: Path) -> None:
    missing = [k for k in keys if k not in section]
    if missing:
        raise ProfileError(f"{path}: in [{name}] fehlen {', '.join(missing)}")


def load_profile(profile_id: str, profiles_dir: Path) -> Profile:
    root = Path(profiles_dir) / profile_id
    path = root / "profil.toml"
    if not path.is_file():
        raise ProfileError(f"Profil '{profile_id}' nicht gefunden: {path}")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"{path}: ungültiges TOML ({exc})") from exc
    repo = data.get("repository", {})
    felder = data.get("felder", {})
    spider = data.get("spider", {})
    crawler = data.get("crawler_tabelle", {})
    _require(repo, _REQUIRED_REPOSITORY, "repository", path)
    _require(felder, REQUIRED_FELDER, "felder", path)
    _require(spider, _REQUIRED_SPIDER, "spider", path)
    _require(crawler, _REQUIRED_CRAWLER, "crawler_tabelle", path)
    return Profile(
        id=str(data.get("id") or profile_id),
        name=str(data.get("name") or profile_id),
        root=root,
        repo_url=str(repo["url"]).rstrip("/"),
        search_url=str(repo["search_url"]).rstrip("/"),
        mds=str(repo["mds"]),
        vocab_sources_url=str(repo["vocab_sources_url"]),
        quelle_property=str(repo["quelle_property"]),
        quelle_werte=tuple(repo["quelle_werte"]),
        felder=MappingProxyType({k: str(v) for k, v in felder.items()}),
        qualitaet=tuple((str(lbl), str(prop)) for lbl, prop in data.get("qualitaet", {}).get("felder", [])),
        spider_kennung=str(spider["kennung_enthaelt"]),
        ignore_spiders=frozenset(spider["ignorieren"]),
        migration_spiders=frozenset(spider["migration"]),
        migration_quelle=str(spider["migration_quelle"]),
        platzhalter_bq=frozenset(spider["platzhalter_bezugsquellen"]),
        lrt_quelle_stichwort=str(spider["lrt_quelle_stichwort"]),
        publiziert_wf=tuple(spider["publiziert_wf_status"]),
        crawler_spalten=MappingProxyType(dict(crawler["spalten"])),
        crawler_spider_spalte=str(crawler["spider_spalte"]),
        crawler_quelldatensatz_spalte=str(crawler["quelldatensatz_spalte"]),
        branding=MappingProxyType(dict(data.get("branding", {}))),
    )


@lru_cache(maxsize=1)
def get() -> Profile:
    """The active profile: QE_PROFILE (default 'wlo') from QE_PROFILES_DIR (default <repo>/profiles)."""
    profile_id = os.environ.get("QE_PROFILE", "").strip() or "wlo"
    profiles_dir = Path(os.environ.get("QE_PROFILES_DIR", "").strip() or DEFAULT_PROFILES_DIR)
    return load_profile(profile_id, profiles_dir)


def reset() -> None:
    """Forget the cached profile (tests, or after changing QE_PROFILE)."""
    get.cache_clear()
