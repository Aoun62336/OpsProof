"""Restoration and fault-hypothesis proof have separate acceptance outcomes."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest

from scripts.m6 import trial_evidence, verify_local_trial
from scripts.m6.scenario_adapters import WorkerFailure


@pytest.mark.parametrize(
    "attempts,logs,expected", [(1, True, False), (2, False, False), (2, True, True)]
)
def test_restored_worker_can_fail_its_hypothesis_without_retaining_a_cleanup_lock(
    tmp_path, monkeypatch, attempts, logs, expected
):
    now = datetime.now(UTC)
    stamp = lambda seconds: (now - timedelta(seconds=seconds)).isoformat()  # noqa: E731
    trial, dispatch, observer, job = (str(uuid4()) for _ in range(4))
    state = {
        "scenario": "worker_failure",
        "trial_id": trial,
        "dispatch_id": dispatch,
        "target_uid": "original-deployment",
        "worker_image": "reviewed:image",
        "old_worker": {"uid": "old-pod"},
        "job_ids": [job],
        "submitted_keys": ["job-key"],
        "inventory_cutoff": stamp(20),
        "inventory_before": {"count": 4},
        "dispatch_intent_at": stamp(12),
        "cleanup_started_at": stamp(2),
    }
    observed = tmp_path / "observer"
    observed.mkdir()
    identity = {
        "trial_id": trial,
        "observer_id": observer,
        "target_uid": state["target_uid"],
        "started_at": stamp(15),
    }
    (observed / "identity.json").write_text(json.dumps(identity))
    (observed / "finished.json").write_text(json.dumps(identity))
    samples = [
        {"at": stamp(13), "worker_pods": [{"uid": "old-pod", "ready": True}]},
        {"at": stamp(7), "worker_pods": [{"uid": "new-pod", "ready": True}]},
    ]
    (observed / "samples.jsonl").write_text("\n".join(json.dumps(row) for row in samples))
    (tmp_path / "source.json").write_text(json.dumps({"tree_sha256": "same-source"}))
    worker = {
        "metadata": {"uid": state["target_uid"]},
        "spec": {"template": {"spec": {"containers": [{"image": state["worker_image"]}]}}},
    }
    environment = SimpleNamespace(
        output=tmp_path / "independent",
        baseline=lambda: {"healthy": True},
        get=lambda kind, *_args: (
            {"items": [{"metadata": {"uid": "new-pod"}}]} if kind == "pods" else worker
        ),
    )
    durable = {
        "id": job,
        "idempotency_key": "job-key",
        "status": "completed",
        "duration_ms": 2000,
        "attempts": attempts,
        "created_at": stamp(10),
        "started_at": stamp(9),
        "completed_at": stamp(4),
    }
    monkeypatch.setattr(
        verify_local_trial, "source_identity", lambda: {"tree_sha256": "same-source"}
    )
    monkeypatch.setattr(verify_local_trial, "durable_jobs", lambda *_args: [durable])
    monkeypatch.setattr(
        verify_local_trial, "durable_inventory", lambda *_args: state["inventory_before"]
    )
    monkeypatch.setattr(verify_local_trial, "http", lambda *_args: (200, durable))
    monkeypatch.setattr(verify_local_trial, "prometheus", lambda *_args: {"fresh": True})
    monkeypatch.setattr(
        verify_local_trial, "telemetry", lambda *_args: {"logs_relevant": logs, "traces": []}
    )
    result = verify_local_trial.verify(environment, state, run_directory=tmp_path)
    assert result["cleanup_verified"] is True
    assert result["hypothesis_verified"] is expected
    assert result["verification_receipt"]["hypothesis_verified"] is expected


def test_uninterrupted_job_does_not_trigger_a_duplicate_submission(monkeypatch):
    replacement = {
        "metadata": {"uid": "new", "labels": {"opsproof.io/role": "worker"}},
        "status": {"phase": "Running"},
    }
    adapter = WorkerFailure(SimpleNamespace(get=lambda *_args: {"items": [replacement]}))
    adapter.state["old_worker"] = {"uid": "old"}
    monkeypatch.setattr(adapter, "wait_jobs", lambda: [{"attempts": 1, "status": "completed"}])
    result = adapter.observe()
    assert result["hypothesis_observed"] is False


def test_dependency_telemetry_without_submitted_jobs_reports_missing_evidence(monkeypatch):
    monkeypatch.setattr(trial_evidence, "http", lambda *_args: (200, {"data": {"result": []}}))
    environment = SimpleNamespace(save=lambda *_args: None)
    result = trial_evidence.telemetry(
        environment,
        {
            "scenario": "downstream_latency",
            "injection_started_at": datetime.now(UTC).isoformat(),
            "job_ids": [],
        },
    )
    assert result["downstream_linked"] is False
    assert result["downstream_timeout"] is False
