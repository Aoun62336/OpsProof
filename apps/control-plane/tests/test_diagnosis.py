"""Policy decisions fail closed independently of model output."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest

from opsproof_control.diagnosis import Snapshot, allowed_recovery, deterministic, model_facts


def sample() -> Snapshot:
    return Snapshot(
        observed_at=datetime.now(UTC),
        incident_fingerprint="a" * 16,
        alert_name="OpsProofDemoQueueBacklog",
        target="opsproof-demo-api",
        incident_status="firing",
        scrape_fresh=True,
        api_ready=True,
        queued=5,
        processing=0,
        worker_paused=True,
        hold_ttl_seconds=120,
        run_id=UUID(int=1),
        job_ids=[UUID(int=2)],
    )


def test_eligible() -> None:
    s = sample()
    assert allowed_recovery(s, deterministic(s))[0]


@pytest.mark.parametrize(
    "field,value",
    [
        ("observed_at", datetime.now(UTC) - timedelta(minutes=2)),
        ("observed_at", datetime.now(UTC) + timedelta(minutes=2)),
        ("target", "external-production-system"),
        ("incident_status", "resolved"),
        ("hold_ttl_seconds", 2),
        ("worker_paused", None),
        ("worker_paused", False),
        ("scrape_fresh", False),
        ("api_ready", None),
        ("queued", 0),
        ("job_ids", []),
        ("run_id", None),
        ("errors", ["missing jobs"]),
        ("alert_name", "unknown"),
    ],
)
def test_policy_rechecks_facts(field, value) -> None:
    s = sample()
    baseline = deterministic(s)
    setattr(s, field, value)
    assert not allowed_recovery(s, baseline)[0]
    assert deterministic(s).action == "none"


def test_model_facts_exclude_identifiers() -> None:
    s = sample()
    facts = str(model_facts(s))
    assert s.incident_fingerprint not in facts
    assert str(s.job_ids[0]) not in facts
    assert model_facts(s)["linked_job_count"] == 1
