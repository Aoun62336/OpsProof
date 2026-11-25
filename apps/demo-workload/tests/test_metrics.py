"""Durable state and evidence freshness; no external dependencies."""

from contextlib import contextmanager
from math import isnan
from types import SimpleNamespace
from unittest.mock import MagicMock

from opsproof_demo import metrics


def fixtures(monkeypatch, rows=None, fail=False):
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = rows or []

    @contextmanager
    def connection(**_kwargs):
        if fail:
            raise TimeoutError("owned database fixture")
        yield conn

    monkeypatch.setattr(metrics, "pool", lambda: SimpleNamespace(connection=connection))
    client = MagicMock()
    client.__enter__.return_value = client
    if hasattr(metrics, "Redis"):
        monkeypatch.setattr(
            metrics, "settings", lambda: SimpleNamespace(redis_url="redis://127.0.0.1:1")
        )
        monkeypatch.setattr(metrics.Redis, "from_url", lambda *_a, **_kw: client)
    else:
        monkeypatch.setattr(metrics, "redis_client", lambda: client)
    return client


def test_known_empty_is_zero_and_is_fresh(monkeypatch):
    fixtures(monkeypatch)
    metrics.refresh_state()
    assert metrics.READY._value.get() == 1
    assert metrics.STATE_UPDATED._value.get() > 0
    for state in metrics.ACTIVE_STATES:
        assert metrics.AGES.labels(state=state)._value.get() == 0


def test_database_failure_is_unknown_and_cannot_refresh_evidence(monkeypatch):
    fixtures(monkeypatch)
    metrics.refresh_state()
    previous = metrics.STATE_UPDATED._value.get()
    fixtures(monkeypatch, fail=True)
    metrics.refresh_state()
    assert metrics.READY._value.get() == 0
    assert metrics.STATE_UPDATED._value.get() == previous
    assert isnan(metrics.COUNTS.labels(state="queued")._value.get())
    assert isnan(metrics.AGES.labels(state="queued")._value.get())
    assert metrics.DEPENDENCIES.labels(dependency="postgresql")._value.get() == 0


def test_oldest_age_is_durable_and_redis_failure_is_separate(monkeypatch):
    client = fixtures(
        monkeypatch, rows=[{"status": "queued", "n": 2, "age_seconds": 46, "last_completion": None}]
    )
    client.ping.side_effect = ConnectionError("owned Redis fixture")
    metrics.refresh_state()
    assert metrics.COUNTS.labels(state="queued")._value.get() == 2
    assert metrics.AGES.labels(state="queued")._value.get() == 46
    assert metrics.DEPENDENCIES.labels(dependency="postgresql")._value.get() == 1
    assert metrics.DEPENDENCIES.labels(dependency="redis")._value.get() == 0
    assert metrics.READY._value.get() == 0
