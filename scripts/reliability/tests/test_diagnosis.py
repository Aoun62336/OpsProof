"""Read-oriented M6 signature evaluation cannot expand M4 action authority."""

from datetime import UTC, datetime, timedelta

import pytest
from opsproof_control.reliability_diagnosis import Observation, deterministic_reliability
from pydantic import ValidationError


def observation(**changes):
    defaults = {
        "observed_at": datetime.now(UTC),
        "target": "opsproof-demo",
        "metrics_fresh": True,
        "queue_lag": 25,
        "queue_age_seconds": 10.0,
        "active_workers": 1,
    }
    defaults.update(changes)
    return Observation.model_validate(defaults)


def test_saturated_signature_is_not_a_recovery_approval():
    value = deterministic_reliability(observation())
    assert value.hypothesis == "worker_saturation"
    assert not value.abstained
    assert value.action == "none"
    assert "not_causal_proof" in value.reason


@pytest.mark.parametrize(
    "changes",
    [
        {"metrics_fresh": False},
        {"observed_at": datetime.now(UTC) - timedelta(seconds=61)},
        {"observed_at": datetime.now(UTC) + timedelta(seconds=15)},
        {"collection_errors": ["missing samples"]},
        {"contradictions": ["different clock windows"]},
        {"queue_age_seconds": None},
        {"queue_lag": 0},
        {"active_workers": None},
    ],
)
def test_missing_stale_or_inconsistent_evidence_abstains(changes):
    assert deterministic_reliability(observation(**changes)).abstained


def test_two_competing_signatures_must_abstain():
    obs = observation(db_probe_ok=False, db_connection_errors=5)
    outcome = deterministic_reliability(obs)
    assert outcome.hypothesis == "unknown"
    assert outcome.reason == "multiple_possible_causes"


def test_worker_failure_requires_live_logs_and_queued_work():
    base = dict(active_workers=0, queue_lag=7, queue_age_seconds=0.0, worker_restarts=2)
    assert deterministic_reliability(observation(**base)).abstained
    assert (
        deterministic_reliability(observation(**base, logs_fresh=True)).hypothesis
        == "worker_failure"
    )


def test_downstream_requires_trace_corroboration():
    base = dict(queue_lag=0, active_workers=1, downstream_p95_seconds=0.9, downstream_timeouts=4)
    assert deterministic_reliability(observation(**base)).abstained
    assert (
        deterministic_reliability(observation(**base, traces_fresh=True)).hypothesis
        == "downstream_latency"
    )


def test_arbitrary_target_and_unbounded_metrics_rejected():
    with pytest.raises(ValidationError):
        observation(target="production")
    with pytest.raises(ValidationError):
        observation(queue_lag=-1)
    with pytest.raises(ValidationError):
        observation(unknown_parameter=True)


def test_diagnosis_output_rejects_coerced_approval_like_boolean():
    from opsproof_control.reliability_diagnosis import Finding
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Finding.model_validate(
            {
                "hypothesis": "unknown",
                "abstained": "yes",
                "reason": "missing",
                "supporting_signals": [],
                "action": "none",
            }
        )
