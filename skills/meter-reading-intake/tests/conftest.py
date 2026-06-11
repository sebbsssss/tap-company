"""pytest configuration for meter-reading-intake tests.

Adds the scripts directory to sys.path so imports resolve without package prefix,
matching the Docker deployment layout.
"""

import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


@pytest.fixture(autouse=True)
def redirect_data_dirs(tmp_path, monkeypatch):
    """Redirect all volume-backed directories to tmp_path for tests."""
    monkeypatch.setenv("UTILITY_LOG_DIR", str(tmp_path / "utility-logs"))
    monkeypatch.setenv("METER_STATE_DIR", str(tmp_path / "meter-intake-state"))

    # Stub out the CRM property fetch so tests never make live API calls.
    import property_cache
    monkeypatch.setattr(property_cache, "_INMEM_CACHE", property_cache.SNAPSHOT_PROPERTIES)
