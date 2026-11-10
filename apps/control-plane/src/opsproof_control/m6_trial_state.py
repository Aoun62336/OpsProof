"""Pure M6 trial lifecycle invariants, separate from existing M4/M5 recovery.

No side effects: transactional persistence, outbox, leases and target locks
must be implemented and tested against the accepted final M5 revision.
This transition function is not itself an authorization or fault injector.
"""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from enum import StrEnum
from uuid import UUID


class TrialPhase(StrEnum):
    REQUESTED = "requested"
    PREFLIGHT = "preflight"
    ARMED = "armed"
    INJECTED = "injected"
    OBSERVING = "observing"
    RECOVERING = "recovering"
    VERIFYING = "verifying"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABORTED = "aborted"
    INDETERMINATE = "indeterminate"


ALLOWED = {
    TrialPhase.REQUESTED: frozenset({TrialPhase.PREFLIGHT, TrialPhase.ABORTED}),
    TrialPhase.PREFLIGHT: frozenset({TrialPhase.ARMED, TrialPhase.FAILED, TrialPhase.ABORTED}),
    TrialPhase.ARMED: frozenset({TrialPhase.INJECTED, TrialPhase.FAILED, TrialPhase.ABORTED}),
    TrialPhase.INJECTED: frozenset({TrialPhase.OBSERVING, TrialPhase.RECOVERING,
                                   TrialPhase.INDETERMINATE}),
    TrialPhase.OBSERVING: frozenset({TrialPhase.RECOVERING, TrialPhase.VERIFYING,
                                    TrialPhase.INDETERMINATE}),
    TrialPhase.RECOVERING: frozenset({TrialPhase.VERIFYING, TrialPhase.INDETERMINATE}),
    TrialPhase.VERIFYING: frozenset({TrialPhase.SUCCEEDED, TrialPhase.FAILED,
                                   TrialPhase.INDETERMINATE}),
}


@dataclass(frozen=True)
class TrialRecord:
    id: UUID
    scenario: str
    phase: TrialPhase
    created_at: datetime
    updated_at: datetime
    target: str
    approved_test_scope: bool = False
    cleanup_plan_confirmed: bool = False
    injection_acknowledged: bool = False
    independent_verified: bool = False
    cleanup_verified: bool = False


def transition(record: TrialRecord, next_phase: TrialPhase, *,
               observed_at: datetime | None = None, **evidence: bool) -> TrialRecord:
    now = observed_at or datetime.now(UTC)
    if now.tzinfo is None or record.updated_at.tzinfo is None or now < record.updated_at:
        raise ValueError("Timestamp missing timezone or moving backward")
    if next_phase not in ALLOWED.get(record.phase, frozenset()):
        raise ValueError("Invalid, replayed or terminal-state transition")
    allowed_evidence = frozenset(("approved_test_scope", "cleanup_plan_confirmed",
                                  "injection_acknowledged", "independent_verified",
                                  "cleanup_verified"))
    if not set(evidence).issubset(allowed_evidence) or any(
        type(v) is not bool for v in evidence.values()
    ):
        raise ValueError("Unsupported or mistyped evidence fields")
    updated = replace(record, phase=next_phase, updated_at=now, **evidence)
    if next_phase == TrialPhase.ARMED and not (
        updated.approved_test_scope and updated.cleanup_plan_confirmed
    ):
        raise ValueError("Arming requires explicit scope and cleanup agreement")
    if next_phase == TrialPhase.INJECTED and not updated.injection_acknowledged:
        raise ValueError("Cannot record injection without actuator receipt")
    if next_phase == TrialPhase.SUCCEEDED and not (
        updated.injection_acknowledged and updated.independent_verified
        and updated.cleanup_verified
    ):
        raise ValueError("Success requires injected action, independent proof and cleanup")
    return updated
