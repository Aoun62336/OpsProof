"""M6 read-only, multi-signal hypotheses; NEVER a recovery authorization API.

Unlike M4's deliberately narrow recovery diagnosis, this module accepts generic
sanitized observations for comparative evaluation across six scenario classes.
It cannot manufacture evidence or request an actuator operation.
"""

from datetime import UTC, datetime
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

Hypothesis = Literal[
    "worker_saturation",
    "faulty_release",
    "database_connectivity",
    "worker_failure",
    "downstream_latency",
    "unknown",
]


class Observation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    observed_at: AwareDatetime
    target: Literal["opsproof-demo", "opsproof-reuse-test"]
    metrics_fresh: bool
    logs_fresh: bool = False
    traces_fresh: bool = False
    contradictions: list[str] = Field(default_factory=list, max_length=8)
    collection_errors: list[str] = Field(default_factory=list, max_length=8)
    queue_lag: int | None = Field(default=None, ge=0)
    queue_age_seconds: float | None = Field(default=None, ge=0)
    active_workers: int | None = Field(default=None, ge=0)
    worker_restarts: int | None = Field(default=None, ge=0)
    db_connection_errors: int | None = Field(default=None, ge=0)
    db_probe_ok: bool | None = None
    candidate_error_rate: float | None = Field(default=None, ge=0, le=1)
    rollout_analysis_failed: bool | None = None
    downstream_p95_seconds: float | None = Field(default=None, ge=0)
    downstream_timeouts: int | None = Field(default=None, ge=0)


class Finding(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    hypothesis: Hypothesis
    abstained: bool
    reason: str
    supporting_signals: list[str] = Field(max_length=6)
    action: Literal["none"] = "none"


def deterministic_m6(obs: Observation, *, now: datetime | None = None) -> Finding:
    """Conservative signature matching, not a validated causal diagnosis.

    Never infer root cause from trial label, operator narrative or AI output.
    Multiple plausible signatures and incomplete evidence force abstention.
    """
    observed_now = now if now is not None else datetime.now(UTC)
    age = (observed_now - obs.observed_at).total_seconds()
    if not 0 <= age <= 60 or not obs.metrics_fresh:
        return Finding(
            hypothesis="unknown",
            abstained=True,
            reason="missing_or_stale_metrics",
            supporting_signals=[],
        )
    if obs.collection_errors or obs.contradictions:
        return Finding(
            hypothesis="unknown",
            abstained=True,
            reason="incomplete_or_contradictory_evidence",
            supporting_signals=[],
        )

    candidates: list[tuple[Hypothesis, list[str]]] = []
    if (
        obs.queue_lag is not None
        and obs.queue_lag >= 10
        and obs.queue_age_seconds is not None
        and obs.queue_age_seconds >= 5
        and obs.active_workers is not None
        and obs.active_workers > 0
    ):
        candidates.append(
            ("worker_saturation", ["queue_lag", "queue_age_seconds", "active_workers"])
        )
    if (
        obs.candidate_error_rate is not None
        and obs.candidate_error_rate >= 0.05
        and obs.rollout_analysis_failed is True
    ):
        candidates.append(("faulty_release", ["candidate_error_rate", "rollout_analysis_failed"]))
    if (
        obs.db_probe_ok is False
        and obs.db_connection_errors is not None
        and obs.db_connection_errors > 0
    ):
        candidates.append(("database_connectivity", ["db_probe_ok", "db_connection_errors"]))
    if (
        obs.active_workers == 0
        and obs.worker_restarts is not None
        and obs.worker_restarts > 0
        and obs.logs_fresh
        and obs.queue_lag is not None
        and obs.queue_lag > 0
    ):
        candidates.append(
            ("worker_failure", ["active_workers", "worker_restarts", "logs_fresh", "queue_lag"])
        )
    if (
        obs.downstream_p95_seconds is not None
        and obs.downstream_p95_seconds >= 0.5
        and obs.downstream_timeouts is not None
        and obs.downstream_timeouts > 0
        and obs.traces_fresh
    ):
        candidates.append(
            (
                "downstream_latency",
                ["downstream_p95_seconds", "downstream_timeouts", "traces_fresh"],
            )
        )

    if len(candidates) != 1:
        return Finding(
            hypothesis="unknown",
            abstained=True,
            reason="multiple_possible_causes" if candidates else "insufficient_correlated_signals",
            supporting_signals=[],
        )
    hypothesis, sources = candidates[0]
    return Finding(
        hypothesis=hypothesis,
        abstained=False,
        reason="correlated_signature_only_not_causal_proof",
        supporting_signals=sources,
    )
