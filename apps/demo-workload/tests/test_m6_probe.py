"""The local fault probe is authenticated, opt-in, bounded and read-only."""

from types import SimpleNamespace
from uuid import uuid4

import psycopg
from fastapi.testclient import TestClient

from opsproof_demo import api, m6_probe


def configure(monkeypatch, **changes):
    values = {
        "inspection_key": uuid4().hex,
        "m6_dependency_probe_enabled": True,
        "database_url": "postgresql://opsproof@demo-deps-postgres:5432/opsproof",
    }
    values.update(changes)
    config = SimpleNamespace(**values)
    monkeypatch.setattr(api, "settings", lambda: config)
    return {"X-OpsProof-Inspect-Key": config.inspection_key}


def unexpected(*_args, **_kwargs):
    raise AssertionError("Unauthorized/disabled/remote probes must not connect")


def test_probe_requires_inspection_authority(monkeypatch):
    configure(monkeypatch)
    monkeypatch.setattr(m6_probe.psycopg, "connect", unexpected)
    with TestClient(api.app) as client:
        assert client.get("/api/v1/internal/dependency-probe").status_code == 401


def test_disabled_probe_never_touches_a_database(monkeypatch):
    headers = configure(monkeypatch, m6_dependency_probe_enabled=False)
    monkeypatch.setattr(m6_probe.psycopg, "connect", unexpected)
    with TestClient(api.app) as client:
        assert client.get("/api/v1/internal/dependency-probe", headers=headers).status_code == 404


def test_remote_database_target_is_refused_before_connect(monkeypatch):
    headers = configure(
        monkeypatch, database_url="postgresql://opsproof@unapproved.invalid/opsproof"
    )
    monkeypatch.setattr(m6_probe.psycopg, "connect", unexpected)
    with TestClient(api.app) as client:
        assert client.get("/api/v1/internal/dependency-probe", headers=headers).status_code == 409


def test_probe_errors_are_bounded_and_do_not_disclose_connection_secrets(monkeypatch):
    headers = configure(monkeypatch)
    sentinel = uuid4().hex

    def failed(*_args, **kwargs):
        assert 0 < kwargs["connect_timeout"] <= 3
        assert 0 < kwargs["tcp_user_timeout"] <= 3000
        raise psycopg.OperationalError(sentinel)

    monkeypatch.setattr(m6_probe.psycopg, "connect", failed)
    with TestClient(api.app) as client:
        response = client.get("/api/v1/internal/dependency-probe", headers=headers)
    assert response.status_code == 503
    assert response.json() == {"detail": "Fresh database connection unavailable"}
    assert sentinel not in response.text


def test_fresh_connection_performs_only_a_read(monkeypatch):
    headers = configure(monkeypatch)
    statements = []

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def execute(self, statement):
            statements.append(statement)

    monkeypatch.setattr(m6_probe.psycopg, "connect", lambda *_args, **_kwargs: Connection())
    with TestClient(api.app) as client:
        response = client.get("/api/v1/internal/dependency-probe", headers=headers)
    assert response.status_code == 200
    assert response.json()["ready"] is True
    assert response.json()["connection"] == "fresh"
    assert statements == ["SELECT 1"]


def test_probe_concurrency_is_limited(monkeypatch):
    headers = configure(monkeypatch)
    monkeypatch.setattr(m6_probe.psycopg, "connect", unexpected)
    assert m6_probe.LIMIT.acquire(blocking=False)
    assert m6_probe.LIMIT.acquire(blocking=False)
    try:
        with TestClient(api.app) as client:
            response = client.get("/api/v1/internal/dependency-probe", headers=headers)
        assert response.status_code == 503
        assert response.json() == {"detail": "M6 probe capacity unavailable"}
    finally:
        m6_probe.LIMIT.release()
        m6_probe.LIMIT.release()
