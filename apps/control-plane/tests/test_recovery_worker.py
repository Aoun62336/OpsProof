"""Execution gates and independent proof requirements, with isolated dependencies."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from opsproof_control import recovery_worker as worker
from opsproof_control.benchmark import CASES, make_snapshot


def setup_worker(monkeypatch, *, attempts=1, enabled=True, incident_status="firing"):
    now = datetime.now(UTC)
    row = {
        "id": UUID(int=10),
        "incident_fingerprint": "a" * 16,
        "investigation_id": UUID(int=11),
        "run_id": UUID(int=1),
        "action": "resume_demo_worker",
        "attempts": attempts,
        "expires_at": now + timedelta(seconds=120),
        "approved_at": now,
        "verify_by": now + timedelta(seconds=120),
        "result": {"actuator": "applied"},
    }
    incident = {
        "status": incident_status,
        "target": "opsproof-demo-api",
        "name": "OpsProofDemoQueueBacklog",
        "resolved_at": now,
    }
    experiment = {"status": "verifying", "scenario": "queue-burst", "count": 1}
    investigation = {"snapshot": make_snapshot(CASES[0]).model_dump(mode="json")}
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    conn.execute.return_value.fetchone.side_effect = [
        {**row, "attempts": attempts - 1},
        row,
        incident,
        experiment,
        investigation,
        {"id": row["id"]},
    ]
    pool = MagicMock()
    pool.connection.return_value.__enter__.return_value = conn
    monkeypatch.setattr(worker, "pool", lambda: pool)
    monkeypatch.setattr(
        worker,
        "settings",
        lambda: SimpleNamespace(
            recovery_enabled=enabled,
            target_url="http://demo",
            inspection_key="inspect",
            recovery_key="resume",
        ),
    )
    finish = MagicMock()
    monkeypatch.setattr(worker, "_finish", finish)
    monkeypatch.setattr(worker, "recovery_event", MagicMock())
    client = MagicMock()
    client.get.return_value.json.return_value = {"paused": True, "ttl_seconds": 120}
    client.post.return_value.json.return_value = {"result": "applied"}
    factory = MagicMock()
    factory.return_value.__enter__.return_value = client
    monkeypatch.setattr(worker.httpx, "Client", factory)
    return row, incident, experiment, investigation, conn, client, finish


def test_kill_switch_prevents_actuator(monkeypatch):
    *_, client, finish = setup_worker(monkeypatch, enabled=False)
    worker.execute_next_recovery()
    client.post.assert_not_called()
    assert finish.call_args.args[1] == "failed"


def test_retry_revalidates_resolved_incident(monkeypatch):
    *_, client, finish = setup_worker(monkeypatch, attempts=2, incident_status="resolved")
    worker.execute_next_recovery()
    client.post.assert_not_called()
    assert finish.call_args.args[1] == "indeterminate"


def test_retry_revalidates_expiry(monkeypatch):
    row, *_, client, finish = setup_worker(monkeypatch, attempts=2)
    row["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
    worker.execute_next_recovery()
    client.post.assert_not_called()
    assert finish.call_args.args[1] == "indeterminate"


def test_first_attempt_requires_current_hold(monkeypatch):
    *_, client, finish = setup_worker(monkeypatch)
    client.get.return_value.json.return_value = {"paused": False, "ttl_seconds": 0}
    worker.execute_next_recovery()
    client.post.assert_not_called()
    assert finish.call_args.args[1] == "failed"


def test_acknowledgment_only_starts_verification(monkeypatch):
    row, _, _, _, conn, client, finish = setup_worker(monkeypatch)
    worker.execute_next_recovery()
    assert client.post.call_args.kwargs["json"] == {"recovery_id": str(row["id"])}
    assert any("status='verifying'" in str(c) for c in conn.execute.call_args_list)
    assert not any("status='succeeded'" in str(c) for c in conn.execute.call_args_list)
    finish.assert_not_called()


@pytest.mark.parametrize(
    "hold,job,experiment_state,incident_state,expired,expected",
    [
        (False, "completed", "succeeded", "resolved", False, "succeeded"),
        (True, "completed", "succeeded", "resolved", True, "indeterminate"),
        (False, "queued", "succeeded", "resolved", True, "indeterminate"),
        (False, "completed", "verifying", "resolved", True, "indeterminate"),
        (False, "completed", "succeeded", "firing", True, "indeterminate"),
        (False, "failed", "verifying", "firing", False, "failed"),
        (False, "queued", "verifying", "firing", False, None),
    ],
)
def test_independent_verification(
    monkeypatch, hold, job, experiment_state, incident_state, expired, expected
):
    row, incident, experiment, investigation, conn, client, _ = setup_worker(monkeypatch)
    row["verify_by"] = datetime.now(UTC) + timedelta(seconds=-1 if expired else 60)
    incident["status"] = incident_state
    experiment["status"] = experiment_state
    conn.execute.return_value.fetchall.return_value = [row]
    conn.execute.return_value.fetchone.side_effect = [
        investigation,
        experiment,
        incident,
        {"id": row["id"]},
    ]

    def get(path, **kwargs):
        response = MagicMock()
        response.json.return_value = (
            {"paused": hold} if "worker-state" in path else {"id": str(UUID(int=2)), "status": job}
        )
        return response

    client.get.side_effect = get
    worker.verify_next_recovery()
    client.post.assert_not_called()
    if expected:
        assert worker.recovery_event.call_args.args[2] == expected
    else:
        worker.recovery_event.assert_not_called()
