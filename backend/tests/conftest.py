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
