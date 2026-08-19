"""
tests/conftest.py — shared fixtures for the smoke test suite.

Every test that touches the database MUST use `temp_db_path` (or a fixture
built on it) so it never reads or writes the developer's real
`brand_monitor.db`. The config layer resolves the DB path lazily via
`config.get_db_path()`, so pointing it at a temp file is done through
`config.set_db_path(...)` — and always cleared afterwards so state doesn't
leak between tests.
"""

import sys
import os

import pytest

# Ensure the package is importable regardless of CWD when tests are invoked.
# (Editable/normal install via `pip install -e .` already covers this, but
# this keeps the suite robust if it's ever run against a bare checkout.)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from brand_monitor import config  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_db_path_override():
    """
    Safety net around every test in the suite: whatever set_db_path()
    override a test applies (directly, via temp_db_path, or via the CLI's
    --db flag), always clear it afterwards so no test can leak state into
    the next one or into the developer's real brand_monitor.db.
    """
    yield
    config.set_db_path(None)


@pytest.fixture
def temp_db_path(tmp_path):
    """
    Point brand_monitor.config at a throwaway SQLite file for the duration
    of a single test, then clear the override so later tests (and the
    developer's real database) are unaffected.
    """
    db_file = tmp_path / "test.db"
    config.set_db_path(str(db_file))
    try:
        yield str(db_file)
    finally:
        config.set_db_path(None)


@pytest.fixture
def junk_api_key(monkeypatch):
    """Set a non-functional API key so code paths that require one proceed,
    without ever risking a real credential or a real network call."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-junk-not-a-real-key")
    yield "sk-test-junk-not-a-real-key"
