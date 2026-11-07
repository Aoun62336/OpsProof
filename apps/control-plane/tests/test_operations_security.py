"""Authentication and explicit spending/recovery gates."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from opsproof_control import api, auth, operations

ID = str(UUID(int=1))


@pytest.mark.parametrize(
    "method,path,body",
    [
        ("GET", "/capabilities", None),
        ("POST", "/investigations", {"incident_fingerprint": "a" * 16}),
        ("POST", "/recoveries", {"investigation_id": ID}),
        ("POST", f"/recoveries/{ID}/approve", {"confirmation": "APPROVE DEMO WORKER RESUME"}),
        ("POST", f"/recoveries/{ID}/reject", None),
        ("POST", f"/investigations/{ID}/ai", None),
    ],
)
def test_missing_credentials(method, path, body) -> None:
    with TestClient(api.app) as client:
        response = client.request(
            method, "/api/v1" + path, json=body, headers={"Idempotency-Key": "unauthorized-test"}
        )
    assert response.status_code == 401


def test_disabled_flags_reject_authenticated_requests(monkeypatch) -> None:
    config = SimpleNamespace(api_key="unit-key", recovery_enabled=False, ai_enabled=False)
    monkeypatch.setattr(auth, "settings", lambda: config)
    monkeypatch.setattr(operations, "settings", lambda: config)
    with TestClient(api.app) as client:
        headers = {"X-OpsProof-Key": "unit-key", "Idempotency-Key": "disabled-test"}
        assert (
            client.post(
                "/api/v1/recoveries", headers=headers, json={"investigation_id": ID}
            ).status_code
            == 403
        )
        assert client.post(f"/api/v1/investigations/{ID}/ai", headers=headers).status_code == 403


def test_benchmark_cases() -> None:
    from opsproof_control.benchmark import CASES, make_snapshot
    from opsproof_control.diagnosis import deterministic

    assert len(CASES) == 10
    for case in CASES:
        result = deterministic(make_snapshot(case))
        assert (result.cause, result.action) == case[-2:]


class QueueConnection:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.statements = []

    def execute(self, sql, params=()):
        self.statements.append(sql)
        return SimpleNamespace(fetchone=lambda: next(self.rows))


@contextmanager
def connection(conn):
    yield conn


@pytest.mark.parametrize("already_requested", [False, True])
def test_ai_quota_serialized_and_duplicate_not_charged(monkeypatch, already_requested):
    row = {"status": "ready", "ai_status": "ready" if already_requested else "not_requested"}
    conn = QueueConnection([row, {"n": 10}])
    monkeypatch.setattr(
        operations, "pool", lambda: SimpleNamespace(connection=lambda: connection(conn))
    )
    monkeypatch.setattr(
        operations, "settings", lambda: SimpleNamespace(ai_enabled=True, ai_daily_limit=10)
    )
    if already_requested:
        assert operations.queue_ai(UUID(ID)) == row
        assert len(conn.statements) == 2
    else:
        with pytest.raises(HTTPException) as error:
            operations.queue_ai(UUID(ID))
        assert error.value.status_code == 429
    assert "pg_advisory_xact_lock" in conn.statements[0]
    assert not any(sql.startswith("UPDATE") for sql in conn.statements)


@pytest.mark.parametrize(
    "status,seconds", [("pending_approval", -1), ("rejected", 120), ("approved", 120)]
)
def test_invalid_approval_state_never_updates(monkeypatch, status, seconds):
    conn = QueueConnection(
        [{"status": status, "expires_at": datetime.now(UTC) + timedelta(seconds=seconds)}]
    )
    monkeypatch.setattr(
        operations, "pool", lambda: SimpleNamespace(connection=lambda: connection(conn))
    )
    monkeypatch.setattr(operations, "settings", lambda: SimpleNamespace(recovery_enabled=True))
    with pytest.raises(HTTPException) as error:
        operations.approve_recovery(
            UUID(ID), operations.Approval(confirmation="APPROVE DEMO WORKER RESUME")
        )
    assert error.value.status_code == 409
    assert not any(sql.startswith("UPDATE") for sql in conn.statements)
