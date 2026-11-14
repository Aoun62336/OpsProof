from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from opsproof_control.m6_trial_state import TrialPhase, TrialRecord, transition


def new_trial():
    ts = datetime.now(UTC)
    return TrialRecord(
        id=UUID(int=1),
        scenario="worker_failure",
        phase=TrialPhase.REQUESTED,
        created_at=ts,
        updated_at=ts,
        target="opsproof-demo/Deployment/demo-worker",
    )


def test_valid_transition_requires_explicit_test_scope_and_cleanup():
    trial = transition(new_trial(), TrialPhase.PREFLIGHT)
    with pytest.raises(ValueError):
        transition(trial, TrialPhase.ARMED)
    trial = transition(
        trial, TrialPhase.ARMED, approved_test_scope=True, cleanup_plan_confirmed=True
    )
    with pytest.raises(ValueError):
        transition(trial, TrialPhase.INJECTED)
    trial = transition(trial, TrialPhase.INJECTED, injection_acknowledged=True)
    trial = transition(trial, TrialPhase.OBSERVING)
    trial = transition(trial, TrialPhase.RECOVERING)
    trial = transition(trial, TrialPhase.VERIFYING)
    with pytest.raises(ValueError):
        transition(trial, TrialPhase.SUCCEEDED)
    trial = transition(
        trial, TrialPhase.SUCCEEDED, independent_verified=True, cleanup_verified=True
    )
    with pytest.raises(ValueError):
        transition(trial, TrialPhase.ARMED)


def test_failed_trial_still_does_not_claim_cleanup_or_success():
    trial = transition(new_trial(), TrialPhase.PREFLIGHT)
    trial = transition(trial, TrialPhase.FAILED)
    assert not trial.cleanup_verified
    with pytest.raises(ValueError):
        transition(trial, TrialPhase.SUCCEEDED)


def test_invalid_clock_and_evidence_rejected():
    trial = new_trial()
    with pytest.raises(ValueError):
        transition(
            trial,
            TrialPhase.PREFLIGHT,
            observed_at=trial.updated_at - timedelta(seconds=1),
        )
    with pytest.raises(ValueError):
        transition(trial, TrialPhase.PREFLIGHT, injection_acknowledged=1)
    with pytest.raises(ValueError):
        transition(trial, TrialPhase.PREFLIGHT, unrelated=True)
