"""Shared test fixtures. Sets a team password BEFORE importing the app so the team tier (2) is
testable; the app/config read it at import time."""
import os

os.environ.setdefault("QE_TEAM_PASSWORD", "test-team-pw")

import pytest
from fastapi.testclient import TestClient

import app as app_module


@pytest.fixture
def client():
    # The context manager runs the lifespan, which loads data/truth.json into memory.
    with TestClient(app_module.app) as c:
        yield c


@pytest.fixture
def team_pw():
    return "test-team-pw"


@pytest.fixture
def tier1(monkeypatch):
    """Tier 1 is fail-closed: set its password and return the header that unlocks it."""
    import config
    monkeypatch.setattr(config, "TIER1_PW", "test-tier1-pw")
    return {"X-Tier1-Password": "test-tier1-pw"}
