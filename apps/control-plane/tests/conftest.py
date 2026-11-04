"""Shared pytest fixtures for the control-plane test suite.

Provides three things required for isolated unit tests:

1. Dummy environment variables so pydantic-settings can construct a
   Settings() instance without a real database or Redis connection.
   The values are intentionally unreachable so no test accidentally
   exercises a live dependency.

2. A pool stub so route handlers that reach the DB layer receive a
   well-formed FastAPI 503 response rather than a PoolClosed exception
   escaping through TestClient's raise_server_exceptions boundary.

3. lru_cache teardown so each test starts with a clean settings() and
   pool() instance rather than inheriting state from a previous test.
"""

from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException


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
    """Replace the real pool with a stub that raises HTTP 503.

    psycopg_pool raises PoolClosed (not an HTTP exception) when the pool
    was created with open=False and open() was never called.  TestClient
    re-raises that as a Python exception rather than returning a response,
    which prevents the test from asserting on the status code.

    By raising HTTPException(503) from the context-manager entry point we
    ensure FastAPI's own exception handler converts it to a 503 response
    before TestClient ever sees the exception boundary.
    """
    _cm = MagicMock()
    _cm.__enter__ = MagicMock(
        side_effect=HTTPException(
            status_code=503,
            detail="dependency unavailable",
        )
    )
    _cm.__exit__ = MagicMock(return_value=False)

    _mock_pool = MagicMock()
    _mock_pool.connection.return_value = _cm

    monkeypatch.setattr("opsproof_control.api.pool", lambda: _mock_pool)
    monkeypatch.setattr("opsproof_control.auth.pool", lambda: _mock_pool)


@pytest.fixture(autouse=True)
def _clear_lru_caches() -> None:
    """Reset cached singletons between tests."""
    yield
    from opsproof_control.config import settings
    from opsproof_control.db import pool, redis_client

    settings.cache_clear()
    pool.cache_clear()
    redis_client.cache_clear()
