"""Shared fixtures for occupancy tests."""

import sys
from pathlib import Path

# Ensure the repo root is on the path so `occupancy` package is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from occupancy.crm_client import load_from_fixtures

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def data():
    return load_from_fixtures(FIXTURES_DIR)
