"""Shared pytest fixtures for the control-plane test suite.

Provides two things required for isolated unit tests:

1. Dummy environment variables so pydantic-settings can construct a
   Settings() instance without a real database or Redis connection.
   The values are intentionally unreachable so no test accidentally
   exercises a live dependency.

2. lru_cache teardown so each test starts with a clean settings() and
   pool() instance rather than inheriting state from a previous test.
"""

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
def _clear_lru_caches() -> None:
    """Reset cached singletons between tests."""
    yield
    from opsproof_control.config import settings
    from opsproof_control.db import pool, redis_client

    settings.cache_clear()
    pool.cache_clear()
    redis_client.cache_clear()
