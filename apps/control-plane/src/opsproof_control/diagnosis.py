"""Pure evidence contracts, deterministic diagnosis and recovery policy."""

from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Cause = Literal[
    "demo_worker_paused",
    "api_unreachable",
    "dependency_unavailable",
    "queue_stalled_unknown",
    "insufficient_evidence",
]
Action = Literal["resume_demo_worker", "none"]
EvidenceKey = Literal["alert", "scrape", "api", "queue", "worker_hold", "job_ids"]
ALERTS = frozenset(
    (
        "OpsProofDemoAPIUnavailable",
        "OpsProofDemoDependenciesUnavailable",
        "OpsProofDemoQueueBacklog",
    )
)


class Snapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observed_at: AwareDatetime
    incident_fingerprint: str
    alert_name: str
    target: str
    incident_status: Literal["firing", "resolved"]
    scrape_fresh: bool = False
    api_ready: bool | None = None
    queued: int | None = Field(default=None, ge=0, le=1_000_000)
    processing: int | None = Field(default=None, ge=0, le=1_000_000)
    worker_paused: bool | None = None
    hold_ttl_seconds: int | None = Field(default=None, ge=0, le=480)
    run_id: UUID | None = None
    job_ids: list[UUID] = Field(default_factory=list, max_length=8)
    errors: list[str] = Field(default_factory=list, max_length=8)


class Diagnosis(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cause: Cause
    action: Action
    explanation: str = Field(min_length=1, max_length=400)
    evidence: list[EvidenceKey] = Field(max_length=6)


def deterministic(snapshot: Snapshot) -> Diagnosis:
    s = snapshot
    age = (datetime.now(UTC) - s.observed_at).total_seconds()
    cause: Cause = "insufficient_evidence"
    action: Action = "none"
    explanation = "Evidence is incomplete, stale, resolved, or outside the supported demo scope."
    evidence: list[EvidenceKey] = ["alert"]
    if (
        0 <= age <= 60
        and s.target == "opsproof-demo-api"
        and s.incident_status == "firing"
        and s.alert_name in ALERTS
    ):
        if s.alert_name == "OpsProofDemoAPIUnavailable" and s.api_ready is False:
            cause = "api_unreachable"
            explanation = "The demo API could not be reached; the underlying cause is unconfirmed."
            evidence += ["api"]
        elif (
            s.alert_name == "OpsProofDemoDependenciesUnavailable"
            and s.scrape_fresh
            and s.api_ready is False
        ):
            cause = "dependency_unavailable"
            explanation = "The scrapeable demo API reports unavailable dependencies."
            evidence += ["api", "scrape"]
        elif (
            s.alert_name == "OpsProofDemoQueueBacklog"
            and s.scrape_fresh
            and s.api_ready is True
            and s.queued is not None
            and s.queued > 0
        ):
            evidence += ["scrape", "api", "queue"]
            cause = "queue_stalled_unknown"
            explanation = "Queued work is observed, but an eligible worker hold is not confirmed."
            if s.worker_paused is True:
                cause = "demo_worker_paused"
                explanation = "The demo worker hold and queued work are independently observed."
                evidence += ["worker_hold"]
                if (
                    s.run_id
                    and s.job_ids
                    and len(set(s.job_ids)) == len(s.job_ids)
                    and s.hold_ttl_seconds is not None
                    and s.hold_ttl_seconds > 30
                    and not s.errors
                ):
                    action = "resume_demo_worker"
                    evidence += ["job_ids"]
    return Diagnosis(cause=cause, action=action, explanation=explanation, evidence=evidence)


def allowed_recovery(snapshot: Snapshot, baseline: Diagnosis) -> tuple[bool, str]:
    # Recompute from facts: a stored or model-supplied recommendation is insufficient.
    current = deterministic(snapshot)
    allowed = (
        current.action == "resume_demo_worker"
        and baseline.cause == current.cause
        and baseline.action == current.action
    )
    return allowed, "eligible" if allowed else "Fresh eligible deterministic evidence required"


def model_facts(snapshot: Snapshot) -> dict:
    return {
        "alert": snapshot.alert_name if snapshot.alert_name in ALERTS else "unsupported",
        "target_supported": snapshot.target == "opsproof-demo-api",
        "incident_status": snapshot.incident_status,
        "evidence_fresh": 0 <= (datetime.now(UTC) - snapshot.observed_at).total_seconds() <= 60,
        "scrape_fresh": snapshot.scrape_fresh,
        "api_ready": snapshot.api_ready,
        "queued": snapshot.queued,
        "processing": snapshot.processing,
        "worker_paused": snapshot.worker_paused,
        "hold_ttl_seconds": snapshot.hold_ttl_seconds,
        "linked_run": snapshot.run_id is not None,
        "linked_job_count": len(snapshot.job_ids),
        "linked_jobs_unique": bool(snapshot.job_ids)
        and len(set(snapshot.job_ids)) == len(snapshot.job_ids),
        "collection_errors": bool(snapshot.errors),
        "evidence_contract": {
            "queued": "Waiting job count; null means unknown, zero means observed empty.",
            "processing": "In-flight job count, not consumer count, readiness or worker capacity.",
            "hold_ttl_seconds": "Seconds remaining on the observed worker hold.",
            "freshness": "evidence_fresh is evaluated against the snapshot reference clock.",
            "job_links": "Only count, linkage and uniqueness flags are provided; no identifiers.",
        },
    }
