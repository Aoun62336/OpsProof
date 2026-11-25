"""Offline reliability qualification and provider-neutral evidence validation.

Historical provider execution was retired. This module never calls external APIs.
"""

import argparse
import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from opsproof_control.reliability_diagnosis import (
    DOWNSTREAM_MIN_P95_SECONDS,
    METRICS_MAX_AGE_SECONDS,
    RELEASE_MIN_ERROR_FRACTION,
    SATURATION_MIN_QUEUE_MESSAGES,
    SATURATION_MIN_WAIT_SECONDS,
    Finding,
    Observation,
    deterministic_reliability,
)

SYSTEM = (
    "Classify ONLY the supplied observations by this explicit configured-signature table. "
    "These are signatures, not causal proof; never invent measurements, commands or actions.\n"
    "FIRST: if evidence_contract.freshness.metrics_fresh_at_reference is not true, "
    "or observation.collection_errors or observation.contradictions is nonempty, "
    "return hypothesis=unknown, abstained=true, action=none. "
    "The freshness flag is computed at the supplied evaluation_at reference, not wall-clock now.\n"
    "Otherwise evaluate ALL FIVE predicates below on observation fields. "
    "Missing or null values NEVER satisfy a comparison; false and0 are observed values.\n"
    f"worker_saturation: queue_lag>={SATURATION_MIN_QUEUE_MESSAGES} AND "
    f"queue_age_seconds>={SATURATION_MIN_WAIT_SECONDS} AND active_workers>0.\n"
    f"faulty_release: candidate_error_rate>={RELEASE_MIN_ERROR_FRACTION} "
    "AND rollout_analysis_failed=true.\n"
    "database_connectivity: db_probe_ok=false AND db_connection_errors>0.\n"
    "worker_failure: active_workers=0 AND worker_restarts>0 AND logs_fresh=true AND queue_lag>0.\n"
    f"downstream_latency: downstream_p95_seconds>={DOWNSTREAM_MIN_P95_SECONDS} "
    "AND downstream_timeouts>0 AND traces_fresh=true.\n"
    "If EXACTLY ONE predicate matches, use that hypothesis and abstained=false. "
    "If NONE or MULTIPLE match, use unknown and abstained=true. action is ALWAYS none. "
    "The >= boundaries are inclusive. Do not substitute operator narrative or another statistic: "
    "gateway-wide errors are not candidate-only rate; a trace is not measured p95; "
    "Pod deletion is not a container restart count.\n"
    "Return the supplied schema. reason: ONE complete sentence, aim for80–180 characters, "
    "ending in punctuation; max500 is a ceiling, not a target. State ONE decisive observation "
    "or missing prerequisite, not every excluded hypothesis. "
    "supporting_signals is a sparse citation object: include ONLY2–4 selected existing paths "
    "with value true; OMIT unused paths entirely. Never emit false. At most six keys; "
    "at least one when not abstaining; an empty object is permitted only when abstaining. "
    "The true values mean selected citations, NOT measured field values. "
    "Never cite an absent child: select its "
    "existing parent object instead. A non-abstained finding requires a selected evidence path."
)
SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "hypothesis": {
            "type": "string",
            "enum": [
                "worker_saturation",
                "faulty_release",
                "database_connectivity",
                "worker_failure",
                "downstream_latency",
                "unknown",
            ],
        },
        "abstained": {"type": "boolean"},
        "reason": {"type": "string", "minLength": 1, "maxLength": 500},
        "supporting_signals": {
            "type": "array",
            "maxItems": 6,
            "uniqueItems": True,
            "items": {"type": "string", "minLength": 1},
        },
        "action": {"type": "string", "enum": ["none"]},
    },
    "required": ["hypothesis", "abstained", "reason", "supporting_signals", "action"],
    "oneOf": [
        {"properties": {"abstained": {"const": True}, "hypothesis": {"const": "unknown"}}},
        {
            "properties": {
                "abstained": {"const": False},
                "hypothesis": {
                    "enum": [
                        "worker_saturation",
                        "faulty_release",
                        "database_connectivity",
                        "worker_failure",
                        "downstream_latency",
                    ]
                },
            }
        },
    ],
}


def evaluate_case(case: dict, *, now: datetime | None = None) -> Observation:
    now = now or datetime.now(UTC)
    facts = {"observed_at": now, "target": "opsproof-demo", "metrics_fresh": True}
    facts.update(case["signals"])
    return Observation.model_validate(facts)


def provider_facts(obs: Observation | dict, *, now: datetime | None = None) -> dict:
    """Describe supplied evidence without filling missing measurements or labels."""
    facts = obs.model_dump(mode="json") if isinstance(obs, Observation) else copy.deepcopy(obs)
    reference = facts.get("evaluation_at", (now or datetime.now(UTC)).isoformat())
    observation = facts.get("observation", facts)
    age = None
    try:
        captured = datetime.fromisoformat(observation["observed_at"].replace("Z", "+00:00"))
        clock = datetime.fromisoformat(reference.replace("Z", "+00:00"))
        if captured.utcoffset() is not None and clock.utcoffset() is not None:
            age = (clock - captured).total_seconds()
    except KeyError, TypeError, ValueError, AttributeError:
        pass
    facts["evidence_contract"] = {
        "units": {
            "queue_lag": (
                "undelivered Redis Stream job messages, excluding pending/in-flight entries. "
                "Duplicate job IDs may occur."
            ),
            "queue_age_seconds": "seconds since the oldest waiting job was created",
            "active_workers": "available worker replicas",
            "worker_restarts": "container restarts, not Pod replacements",
            "db_connection_errors": "observed failed connection probes or recorded errors",
            "candidate_error_rate": "fraction from 0 to 1 for candidate-only requests",
            "downstream_p95_seconds": "seconds, measured 95th percentile",
            "downstream_timeouts": "observed timeout count, possibly a lower bound",
        },
        "freshness": {
            "reference_time": reference,
            "observation_age_seconds": age,
            "maximum_age_seconds": METRICS_MAX_AGE_SECONDS,
            "metrics_fresh_at_reference": (
                age is not None
                and 0 <= age <= METRICS_MAX_AGE_SECONDS
                and observation.get("metrics_fresh") is True
            ),
            "rule": (
                "Missing, future or stale metrics require abstention. "
                "Channel flags apply separately."
            ),
        },
        "signature_thresholds": {
            "worker_saturation": {
                "queue_lag_min_messages": SATURATION_MIN_QUEUE_MESSAGES,
                "queue_age_min_seconds": SATURATION_MIN_WAIT_SECONDS,
                "active_workers_greater_than": 0,
            },
            "faulty_release": {
                "candidate_error_fraction_min": RELEASE_MIN_ERROR_FRACTION,
                "rollout_analysis_failed_required": True,
            },
            "database_connectivity": {
                "failed_database_probe_required": True,
                "connection_errors_greater_than": 0,
            },
            "worker_failure": {
                "active_workers": 0,
                "worker_restarts_greater_than": 0,
                "queue_lag_greater_than": 0,
                "fresh_logs_required": True,
            },
            "downstream_latency": {
                "measured_p95_min_seconds": DOWNSTREAM_MIN_P95_SECONDS,
                "positive_timeout_count_and_fresh_traces_required": True,
            },
        },
        "threshold_scope": (
            "Configured signature criteria. Production SLO thresholds are unavailable."
        ),
        "expected_queue_behaviour": (
            "A burst may temporarily increase waiting jobs. Positive backlog alone does not "
            "establish a fault. Correlate waiting age, available workers and recorded evidence. "
            "A drained queue has zero waiting jobs. Pending jobs are already delivered "
            "and may be processing."
        ),
        "grounding": (
            "Cite exact supplied field paths. Thresholds and units describe interpretation. "
            "Missing percentile, rate, restart count or window cannot be inferred from "
            "a different statistic. Findings authorize no action."
        ),
    }
    return facts


def validate_evidence_paths(
    finding: Finding, facts: dict, *, allowed_paths: set[str] | None = None
) -> None:
    """Resolve JSON field paths only. Factual reasoning still requires review."""
    if len(set(finding.supporting_signals)) != len(finding.supporting_signals):
        raise ValueError("Model cited duplicate evidence paths")
    for path in finding.supporting_signals:
        if allowed_paths is not None and path not in allowed_paths:
            raise ValueError("Model cited a field outside the request evidence allowlist")
        value = facts
        for part in path.split("."):
            if isinstance(value, dict) and part in value:
                value = value[part]
            elif isinstance(value, list) and part.isascii() and part.isdecimal():
                index = int(part)
                if index >= len(value):
                    raise ValueError("Model cited a missing evidence path")
                value = value[index]
            else:
                raise ValueError("Model cited a missing evidence path")


def validate_explanation(reason: str) -> None:
    """Reject visibly unfinished text; factual completeness still requires review."""
    if not reason.strip() or len(reason) > 500 or reason.rstrip()[-1] not in ".!?":
        raise ValueError("Model explanation must be bounded and end as a complete sentence")


def benchmark(
    dataset: dict,
    provider: str = "deterministic",
    max_cases: int | None = None,
    api_key: str = "",
) -> dict:
    if provider != "deterministic":
        raise ValueError("External benchmark execution is retired; use offline qualification")
    cases = dataset.get("cases")
    if not isinstance(cases, list) or len(cases) != 20:
        raise ValueError("Frozen qualification dataset must contain exactly 20 cases")
    selected = cases if max_cases is None else cases[:max_cases]
    seen = set()
    report = []
    for case in selected:
        if case["id"] in seen:
            raise ValueError("Duplicate case ID")
        seen.add(case["id"])
        record = {
            "id": case["id"],
            "expected_hypothesis": case["expected_hypothesis"],
            "expected_abstained": case["expected_abstained"],
        }
        try:
            obs = evaluate_case(case)
            diagnosis = deterministic_reliability(obs)
            meta = {"latency_ms": None, "usage": None, "cost_usd": 0}
            record.update(
                {
                    "prediction": diagnosis.model_dump(),
                    "hypothesis_correct": (diagnosis.hypothesis == case["expected_hypothesis"]),
                    "abstention_correct": diagnosis.abstained == case["expected_abstained"],
                    "valid": True,
                    **meta,
                }
            )
        except Exception as exc:
            # Avoid logging provider error bodies or tokens; a failure is a result.
            record.update(
                {
                    "valid": False,
                    "hypothesis_correct": False,
                    "abstention_correct": False,
                    "error_type": type(exc).__name__,
                }
            )
        report.append(record)
    return {
        "dataset_id": dataset["dataset_id"],
        "provider": provider,
        "case_count": len(selected),
        "hypothesis_correct": sum(x["hypothesis_correct"] for x in report),
        "abstention_correct": sum(x["abstention_correct"] for x in report),
        "invalid_or_error": sum(not x["valid"] for x in report),
        "cases": report,
        "limitation": (
            "Synthetic signed-off ground truth; "
            "independent held-out real fault cases still required"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=Path("benchmarks/ai/qualification_v1.json"))
    parser.add_argument("--provider", choices=("deterministic",), default="deterministic")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.max_cases is not None and not 1 <= args.max_cases <= 20:
        parser.error("Max-cases outside dataset")
    raw = args.dataset.read_bytes()
    report = benchmark(json.loads(raw), args.provider, args.max_cases)
    report["dataset_sha256"] = hashlib.sha256(raw).hexdigest()
    report["executed_utc"] = datetime.now(UTC).isoformat()
    report["billing_mode"] = "offline_zero_calls"
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "provider",
                    "case_count",
                    "hypothesis_correct",
                    "abstention_correct",
                    "invalid_or_error",
                )
            },
            indent=2,
        )
    )
    if (
        report["invalid_or_error"]
        or report["hypothesis_correct"] != report["case_count"]
        or report["abstention_correct"] != report["case_count"]
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
