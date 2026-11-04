"""Shared pytest fixtures for the control-plane test suite.

Provides three things required for isolated unit tests:

1. Dummy environment variables so pydantic-settings can construct a
   Settings() instance without a real database or Redis connection.
   The values are intentionally unreachable so no test accidentally
   exercises a live dependency.

2. A pool stub that provides a fully functional mock DB connection so
   route handlers run to completion and return a real HTTP response.
   This properly isolates authentication behaviour from the data layer:
   the route returns 200 (empty list) when auth passes, 401 when it
   fails — without touching a real database at any point.

3. lru_cache teardown so each test starts with a clean settings() and
   pool() instance rather than inheriting state from a previous test.
"""

from unittest.mock import MagicMock

import pytest


@pytest.fixture(autouse=True)
def _unit_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Inject stub connection strings required by pydantic-settings."""
    monkeypatch.setenv(
        "OPSPROOF_CONTROL_DATABASE_URL",
        "postgresql://unit-test:unit-test@127.0.0.1:5999/unit-test",
    )
    monkeypatch.setenv(
        "OPSPROOF_CONTROL_REDIS_URL",
        "redis://127.0.0.1:6399",
    )


@pytest.fixture(autouse=True)
def _stub_pool(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the real pool with a mock that completes requests normally.

    The mock connection returns empty result sets for every query so that
    route handlers run to completion and return a genuine HTTP response
    (200 for authenticated requests, 401 for rejected ones).  This is
    the standard unit-test pattern for FastAPI services: mock the data
    layer at the boundary so business logic — including authentication —
    can be exercised without a real database.
    """
    _mock_conn = MagicMock()
    # fetchall() used by list routes → empty list → serialises to []
    _mock_conn.execute.return_value.fetchall.return_value = []
    # fetchone() used by detail/session routes → None → 404
    _mock_conn.execute.return_value.fetchone.return_value = None

    _cm = MagicMock()
    _cm.__enter__ = MagicMock(return_value=_mock_conn)
    _cm.__exit__ = MagicMock(return_value=False)

    _mock_pool = MagicMock()
    _mock_pool.connection.return_value = _cm
    _mock_pool.open = MagicMock()
    _mock_pool.close = MagicMock()

    monkeypatch.setattr("opsproof_control.api.pool", lambda: _mock_pool)
    monkeypatch.setattr("opsproof_control.auth.pool", lambda: _mock_pool)
    monkeypatch.setattr("opsproof_control.db.pool", lambda: _mock_pool)


@pytest.fixture(autouse=True)
def _clear_lru_caches() -> None:
    """Reset cached singletons between tests."""
    yield
    from opsproof_control.config import settings
    from opsproof_control.db import pool, redis_client

    settings.cache_clear()
    pool.cache_clear()
    redis_client.cache_clear()
