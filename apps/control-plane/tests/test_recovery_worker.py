"""Execution gates and independent proof requirements, with isolated dependencies."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from opsproof_control import recovery_worker as worker
from opsproof_control.benchmark import CASES, make_snapshot
from opsproof_control.diagnosis import deterministic


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
    snapshot = make_snapshot(CASES[0])
    investigation = {
        "status": "ready",
        "snapshot": snapshot.model_dump(mode="json"),
        "baseline": deterministic(snapshot).model_dump(),
    }
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = []
    conn.execute.return_value.fetchone.side_effect = [
        {**row, "attempts": attempts - 1},
        row,
        incident,
        experiment,
        investigation,
        {"status": "firing"},
        {"status": "verifying"},
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
    monkeypatch.setattr(worker, "collect", lambda incident, run_id: snapshot)
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


def test_execution_abstains_on_stale_prometheus_evidence(monkeypatch):
    *_, client, finish = setup_worker(monkeypatch)
    monkeypatch.setattr(worker, "collect", lambda *_: make_snapshot(CASES[5]))
    worker.execute_next_recovery()
    client.post.assert_not_called()
    assert finish.call_args.args[1] == "failed"
    assert "execution-time policy evidence" in finish.call_args.args[2]


def test_execution_rejects_changed_job_identity(monkeypatch):
    *_, client, finish = setup_worker(monkeypatch)
    fresh = make_snapshot(CASES[0]).model_copy(update={"job_ids": [UUID(int=99)]})
    monkeypatch.setattr(worker, "collect", lambda *_: fresh)
    worker.execute_next_recovery()
    client.post.assert_not_called()
    assert finish.call_args.args[1] == "failed"


def test_retry_rejects_missing_hold(monkeypatch):
    *_, client, finish = setup_worker(monkeypatch, attempts=2)
    client.get.return_value.json.return_value = {"paused": False, "ttl_seconds": 0}
    worker.execute_next_recovery()
    client.post.assert_not_called()
    assert finish.call_args.args[1] == "indeterminate"


@pytest.mark.parametrize("payload", [{"result": "unexpected"}, [], {"result": None}])
def test_unknown_actuator_acknowledgment_is_indeterminate(monkeypatch, payload):
    *_, client, finish = setup_worker(monkeypatch)
    client.post.return_value.json.return_value = payload
    worker.execute_next_recovery()
    assert client.post.call_count == 1
    assert finish.call_args.args[1] == "indeterminate"


def test_confirmed_not_paused_is_not_success(monkeypatch):
    *_, client, finish = setup_worker(monkeypatch)
    client.post.return_value.json.return_value = {"result": "not_paused"}
    worker.execute_next_recovery()
    assert finish.call_args.args[1] == "failed"
    assert client.post.call_count == 1


def test_incident_resolves_during_fresh_collection(monkeypatch):
    row, incident, experiment, investigation, conn, client, finish = setup_worker(monkeypatch)
    conn.execute.return_value.fetchone.side_effect = [
        {**row, "attempts": 0},
        row,
        incident,
        experiment,
        investigation,
        {"status": "resolved"},
        {"status": "verifying"},
    ]
    worker.execute_next_recovery()
    client.post.assert_not_called()
    assert finish.call_args.args[1] == "failed"


def test_retry_rejects_stale_scrape_too(monkeypatch):
    *_, client, finish = setup_worker(monkeypatch, attempts=2)
    monkeypatch.setattr(worker, "collect", lambda *_: make_snapshot(CASES[5]))
    worker.execute_next_recovery()
    client.post.assert_not_called()
    assert finish.call_args.args[1] == "indeterminate"


def test_approval_expiring_during_collection_prevents_actuator(monkeypatch):
    row, *_, client, finish = setup_worker(monkeypatch)

    def collect(*args):
        row["expires_at"] = datetime.now(UTC) - timedelta(seconds=1)
        return make_snapshot(CASES[0])

    monkeypatch.setattr(worker, "collect", collect)
    worker.execute_next_recovery()
    client.post.assert_not_called()
    assert finish.call_args.args[1] == "indeterminate"


def test_experiment_finishes_during_collection_prevents_actuator(monkeypatch):
    row, incident, experiment, investigation, conn, client, finish = setup_worker(monkeypatch)
    conn.execute.return_value.fetchone.side_effect = [
        {**row, "attempts": 0},
        row,
        incident,
        experiment,
        investigation,
        {"status": "firing"},
        {"status": "succeeded"},
    ]
    worker.execute_next_recovery()
    client.post.assert_not_called()
    assert finish.call_args.args[1] == "failed"


def test_retry_with_fresh_eligible_evidence_keeps_same_actuator_identity(monkeypatch):
    row, *_, client, finish = setup_worker(monkeypatch, attempts=2)
    client.post.return_value.json.return_value = {"result": "replayed"}
    worker.execute_next_recovery()
    assert client.post.call_args.kwargs["json"] == {"recovery_id": str(row["id"])}
    finish.assert_not_called()
