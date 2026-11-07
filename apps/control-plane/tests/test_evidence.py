"""Experiment success requires exact completed jobs, not just zero pending jobs."""

from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from opsproof_control import evidence


def mocked_run(monkeypatch, *, job_ids, count, responses):
    """No live dependencies; caller controls the authoritative event and job results."""
    conn = MagicMock()
    conn.execute.return_value.fetchone.side_effect = [
        {"status": "verifying", "count": count},
        {"details": {"job_ids": job_ids, "submitted": len(job_ids)}},
        {"id": uuid4()},
    ]
    pool = MagicMock()
    pool.connection.return_value.__enter__.return_value = conn
    monkeypatch.setattr(evidence, "pool", lambda: pool)
    monkeypatch.setattr(evidence, "settings", lambda: SimpleNamespace(target_url="http://unused"))
    failure, recorded = MagicMock(), MagicMock()
    monkeypatch.setattr(evidence, "fail", failure)
    monkeypatch.setattr(evidence, "event", recorded)
    client = MagicMock()

    def get(path):
        response = MagicMock()
        response.json.return_value = responses.get(path.rsplit("/", 1)[-1], {})
        return response

    client.get.side_effect = get
    factory = MagicMock()
    factory.return_value.__enter__.return_value = client
    monkeypatch.setattr(evidence.httpx, "Client", factory)
    return failure, recorded, client


@pytest.mark.parametrize("ids,count", [([], 1), ([str(uuid4())], 2)])
def test_missing_jobs_do_not_succeed(monkeypatch, ids, count):
    failure, recorded, client = mocked_run(monkeypatch, job_ids=ids, count=count, responses={})
    evidence.verify(uuid4())
    failure.assert_called_once()
    recorded.assert_not_called()
    client.get.assert_not_called()


def test_mismatched_identity_never_succeeds(monkeypatch):
    job = str(uuid4())
    failure, recorded, _ = mocked_run(
        monkeypatch,
        job_ids=[job],
        count=1,
        responses={job: {"id": str(uuid4()), "status": "completed"}},
    )
    evidence.verify(uuid4())
    failure.assert_called_once()
    recorded.assert_not_called()


def test_exact_completed_job_succeeds(monkeypatch):
    job = str(uuid4())
    failure, recorded, _ = mocked_run(
        monkeypatch,
        job_ids=[job],
        count=1,
        responses={job: {"id": job, "status": "completed"}},
    )
    evidence.verify(uuid4())
    failure.assert_not_called()
    recorded.assert_called_once()
    assert recorded.call_args.args[2] == "verified"


def test_failed_job_never_succeeds(monkeypatch):
    job = str(uuid4())
    failure, recorded, _ = mocked_run(
        monkeypatch,
        job_ids=[job],
        count=1,
        responses={job: {"id": job, "status": "failed"}},
    )
    evidence.verify(uuid4())
    failure.assert_called_once()
    recorded.assert_not_called()


def test_unknown_job_state_cannot_be_recorded_as_success(monkeypatch):
    job = str(uuid4())
    failure, recorded, _ = mocked_run(
        monkeypatch,
        job_ids=[job],
        count=1,
        responses={job: {"id": job, "status": "not_a_real_state"}},
    )
    evidence.verify(uuid4())
    failure.assert_called_once()
    recorded.assert_not_called()


def test_terminal_state_race_does_not_emit_verified_event(monkeypatch):
    job = str(uuid4())
    failure, recorded, _ = mocked_run(
        monkeypatch,
        job_ids=[job],
        count=1,
        responses={job: {"id": job, "status": "completed"}},
    )
    # Another worker has already made the run terminal before the guarded UPDATE.
    conn = evidence.pool().connection.return_value.__enter__.return_value
    conn.execute.return_value.fetchone.side_effect = [
        {"status": "verifying", "count": 1},
        {"details": {"job_ids": [job], "submitted": 1}},
        None,
    ]
    evidence.verify(uuid4())
    failure.assert_not_called()
    recorded.assert_not_called()
