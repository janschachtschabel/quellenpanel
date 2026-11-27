"""Etappe 3 / Task 8: one version source (backend/pyproject.toml)."""
import tomllib
from pathlib import Path

import config

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_version_comes_from_pyproject():
    project = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]
    assert config.VERSION == project["version"] == "1.0.0"


def test_openapi_reports_version(client):
    assert client.get("/openapi.json").json()["info"]["version"] == "1.0.0"


def test_missing_pyproject_falls_back(tmp_path):
    assert config._read_version(tmp_path / "fehlt.toml") == "0.0.0"


def test_pyproject_goes_into_the_image():
    ignored = (PYPROJECT.parents[1] / ".dockerignore").read_text(encoding="utf-8").splitlines()
    assert "backend/pyproject.toml" not in ignored and "**/*.toml" not in ignored
