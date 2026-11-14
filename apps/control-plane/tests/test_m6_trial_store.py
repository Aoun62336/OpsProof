"""Non-database M6 unit checks. PostgreSQL concurrency needs separate integration tests."""

from datetime import UTC, datetime
from uuid import UUID

import pytest

from opsproof_control.m6_trial_state import TrialPhase
from opsproof_control.m6_trial_store import (
    TrialConflict,
    _assert_fence,
    _move,
    attach_artifact,
    mark_uncertain,
    request_abort,
)


class Result:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class FakeConn:
    def __init__(self, phase="preflight", acknowledged=False):
        now = datetime.now(UTC)
        self.row = {
            "id": UUID(int=10),
            "scenario": "worker_failure",
            "phase": phase,
            "created_at": now,
            "updated_at": now,
            "target": "opsproof-demo/Deployment/demo-worker",
            "approved_test_scope": phase not in ("requested", "preflight"),
            "cleanup_plan_confirmed": phase not in ("requested", "preflight"),
            "injection_acknowledged": acknowledged,
            "independent_verified": False,
            "cleanup_verified": False,
        }
        self.sql = []

    def execute(self, sql, params=None):
        self.sql.append((sql, params))
        if sql == "SELECT clock_timestamp() AS now":
            return Result({"now": datetime.now(UTC)})
        if sql.startswith("SELECT fence_token FROM m6_target_leases"):
            return Result({"fence_token": UUID(int=20)})
        if sql.startswith("SELECT * FROM m6_trials"):
            return Result(dict(self.row))
        if "UPDATE m6_trials SET phase=" in sql:
            (phase, updated_at, approved, cleanup, *rest) = params
            self.row.update(
                {
                    "phase": phase,
                    "updated_at": updated_at,
                    "approved_test_scope": approved,
                    "cleanup_plan_confirmed": cleanup,
                }
            )
            return Result(dict(self.row))
        if "UPDATE m6_trials SET injection_acknowledged=" in sql:
            self.row.update(
                zip(
                    ("injection_acknowledged", "independent_verified", "cleanup_verified"),
                    params[:3],
                    strict=True,
                )
            )
            return Result(dict(self.row))
        if "UPDATE m6_trials SET abort_requested" in sql:
            self.row["abort_requested"] = True
            return Result(dict(self.row))
        return Result()


def test_abort_before_injection_is_terminal_and_releases_reservation():
    conn = FakeConn(phase="preflight")
    row = request_abort(conn, UUID(int=10))
    assert row["phase"] == TrialPhase.ABORTED
    assert any("DELETE FROM m6_target_leases" in sql for sql, _ in conn.sql)


def test_abort_after_injection_does_not_pretend_cleanup():
    conn = FakeConn(phase="injected", acknowledged=True)
    row = request_abort(conn, UUID(int=10))
    assert row["phase"] == "injected"
    assert row["abort_requested"] is True
    assert not any("DELETE FROM m6_target_leases" in sql for sql, _ in conn.sql)


def test_unverified_trial_cannot_succeed():
    conn = FakeConn(phase="verifying", acknowledged=True)
    with pytest.raises(ValueError):
        _move(conn, conn.row, TrialPhase.SUCCEEDED)
    assert not any("UPDATE m6_trials SET phase=" in sql for sql, _ in conn.sql)


def test_terminal_trial_cannot_be_aborted_again():
    conn = FakeConn(phase="aborted")
    with pytest.raises(TrialConflict):
        request_abort(conn, UUID(int=10))


def test_stale_token_rejected():
    conn = FakeConn(phase="armed")
    with pytest.raises(TrialConflict):
        _assert_fence(conn, UUID(int=10), UUID(int=21))


def test_uncertain_injection_retains_target_reservation():
    conn = FakeConn(phase="injected", acknowledged=True)
    result = mark_uncertain(
        conn,
        UUID(int=10),
        fence_token=UUID(int=20),
        reason="actuator response unknown",
    )
    assert result["phase"] == "indeterminate"
    assert not any("DELETE FROM m6_target_leases" in sql for sql, _ in conn.sql)


def test_artifact_relative_path_cannot_escape_evidence_directory():
    conn = FakeConn(phase="verifying", acknowledged=True)
    with pytest.raises(ValueError):
        attach_artifact(
            conn,
            UUID(int=10),
            fence_token=UUID(int=20),
            kind="independent",
            relative_path=".runtime/m6/../secret",
            sha256="a" * 64,
        )


def test_fence_lock_order_is_trial_then_target():
    """Keep lock acquisition aligned with abort and expiry operations."""
    conn = FakeConn(phase="injected", acknowledged=True)
    _assert_fence(conn, UUID(int=10), UUID(int=20))
    locked = [sql for sql, _ in conn.sql if "FOR UPDATE" in sql]
    assert len(locked) >= 2
    assert locked[0].startswith("SELECT * FROM m6_trials WHERE id=%s FOR UPDATE")
    assert locked[1].startswith("SELECT fence_token FROM m6_target_leases")


def test_verifying_phase_can_be_marked_uncertain_without_releasing_target():
    conn = FakeConn(phase="verifying", acknowledged=True)
    result = mark_uncertain(
        conn, UUID(int=10), fence_token=UUID(int=20), reason="cleanup evidence lost"
    )
    assert result["phase"] == "indeterminate"
    assert not any("DELETE FROM m6_target_leases" in sql for sql, _ in conn.sql)
