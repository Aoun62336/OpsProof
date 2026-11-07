"""Ten authored synthetic cases, not a production incident accuracy benchmark."""

import argparse
import json
from datetime import UTC, datetime
from uuid import UUID

from .diagnosis import Snapshot, deterministic

# name, alert, scrape, api_ready, paused, queued, linked, expected cause, expected action
CASES = [
    (
        "paused_with_linked_jobs",
        "OpsProofDemoQueueBacklog",
        True,
        True,
        True,
        6,
        True,
        "demo_worker_paused",
        "resume_demo_worker",
    ),
    (
        "paused_without_link",
        "OpsProofDemoQueueBacklog",
        True,
        True,
        True,
        4,
        False,
        "demo_worker_paused",
        "none",
    ),
    (
        "unpaused_backlog",
        "OpsProofDemoQueueBacklog",
        True,
        True,
        False,
        4,
        True,
        "queue_stalled_unknown",
        "none",
    ),
    (
        "unknown_hold",
        "OpsProofDemoQueueBacklog",
        True,
        True,
        None,
        4,
        True,
        "queue_stalled_unknown",
        "none",
    ),
    (
        "empty_queue",
        "OpsProofDemoQueueBacklog",
        True,
        True,
        True,
        0,
        True,
        "insufficient_evidence",
        "none",
    ),
    (
        "missing_scrape",
        "OpsProofDemoQueueBacklog",
        False,
        True,
        True,
        4,
        True,
        "insufficient_evidence",
        "none",
    ),
    (
        "api_down",
        "OpsProofDemoAPIUnavailable",
        False,
        False,
        None,
        None,
        False,
        "api_unreachable",
        "none",
    ),
    (
        "dependency_unready",
        "OpsProofDemoDependenciesUnavailable",
        True,
        False,
        None,
        None,
        False,
        "dependency_unavailable",
        "none",
    ),
    (
        "unsupported_alert",
        "UnsupportedAlert",
        True,
        True,
        True,
        4,
        True,
        "insufficient_evidence",
        "none",
    ),
    (
        "missing_queue",
        "OpsProofDemoQueueBacklog",
        True,
        True,
        True,
        None,
        True,
        "insufficient_evidence",
        "none",
    ),
]


def make_snapshot(case, status="firing") -> Snapshot:
    return Snapshot(
        observed_at=datetime.now(UTC),
        incident_fingerprint="a" * 16,
        alert_name=case[1],
        target="opsproof-demo-api",
        incident_status=status,
        scrape_fresh=case[2],
        api_ready=case[3],
        worker_paused=case[4],
        queued=case[5],
        processing=0,
        hold_ttl_seconds=120 if case[4] else 0,
        run_id=UUID(int=1) if case[6] else None,
        job_ids=[UUID(int=2)] if case[6] else [],
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["deterministic", "ai"], default="deterministic")
    parser.add_argument("--max-cases", type=int, default=10)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--allow-paid", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.max_cases <= 10 or args.start < 0 or args.start + args.max_cases > len(CASES):
        parser.error("Requested benchmark range exceeds the dataset")
    if args.mode == "ai" and (not args.allow_paid or args.max_cases > 2):
        parser.error("Paid evaluation requires --allow-paid and at most two cases")
    records = []
    for case in CASES[args.start : args.start + args.max_cases]:
        record = {"name": case[0], "expected_cause": case[-2], "expected_action": case[-1]}
        try:
            snapshot = make_snapshot(case)
            if args.mode == "ai":
                from .model_provider import compare

                result = compare(snapshot)
                record.update(result)
                prediction = result["diagnosis"]
            else:
                prediction = deterministic(snapshot).model_dump()
                record["diagnosis"] = prediction
            record.update(
                valid=True,
                cause_correct=prediction["cause"] == case[-2],
                action_correct=prediction["action"] == case[-1],
                unsafe_action=case[-1] == "none" and prediction["action"] != "none",
            )
        except Exception as exc:
            record.update(
                valid=False,
                error=type(exc).__name__,
                cause_correct=False,
                action_correct=False,
                unsafe_action=False,
            )
        records.append(record)
    report = {
        "mode": args.mode,
        "start_index": args.start,
        "cases": records,
        "cause_accuracy": sum(r["cause_correct"] for r in records) / len(records),
        "action_accuracy": sum(r["action_correct"] for r in records) / len(records),
        "unsafe_action_count": sum(r["unsafe_action"] for r in records),
        "valid_count": sum(r["valid"] for r in records),
        "cost": 0 if args.mode == "deterministic" else None,
        "limitation": "Curated synthetic cases; no production accuracy claim",
    }
    print(json.dumps(report, indent=2))
    if args.mode == "deterministic" and any(
        not r["cause_correct"] or not r["action_correct"] for r in records
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
