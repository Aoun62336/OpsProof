"""Independently reconcile bounded k6 receipts with durable demo job state.

Read-only HTTP GETs. Requires a real M5 port-forward to 127.0.0.1:18088.
Never equate k6 HTTP 202 with durable processing completion.
"""

import argparse
import json
import math
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

ALLOWED_BASES = frozenset(("http://127.0.0.1:18088", "http://localhost:18088"))


def parse_receipts(path: Path, run_id: str, expected_count: int) -> list[str]:
    if not 1 <= expected_count <= 120:
        raise ValueError("Expected count outside 1..120")
    receipts = []
    for line in path.read_text(encoding="utf-8").splitlines():
        start = line.find('{"kind":"m6_job_receipt"')
        if start < 0:
            continue
        record, _ = json.JSONDecoder().raw_decode(line[start:])
        if record.get("run_id") != run_id:
            raise ValueError("Foreign trial receipt present; use a single-run log")
        receipts.append(record)
    if len(receipts) != expected_count:
        raise ValueError(f"Receipt count mismatch: {len(receipts)} != {expected_count}")
    if any(r.get("accepted") is not True or r.get("status") != 202 for r in receipts):
        raise ValueError("At least one k6 job submission failed")
    keys = [r.get("key") for r in receipts]
    ids = [str(UUID(str(r.get("id")))) for r in receipts]
    if len(set(keys)) != expected_count or len(set(ids)) != expected_count:
        raise ValueError("Duplicate idempotency key or job ID")
    return ids


def get_job(base: str, job_id: str) -> dict:
    request = Request(f"{base}/api/v1/jobs/{job_id}", headers={"Accept": "application/json"})
    with urlopen(request, timeout=5) as response:
        if response.status != 200:
            raise ValueError(f"Job endpoint returned {response.status}")
        result = json.load(response)
    if str(UUID(str(result.get("id")))) != job_id:
        raise ValueError("Job ID mismatched response")
    return result


def percentile_nearest_rank(values: list[float], percentage: int) -> float:
    if not values or not 1 <= percentage <= 100:
        raise ValueError("Invalid percentile request")
    ordered = sorted(values)
    return ordered[math.ceil(len(values) * percentage / 100) - 1]


def duration_seconds(record: dict) -> float:
    def timestamp(value):
        if not value:
            raise ValueError("Completed job lacks timestamp")
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("Job timestamp missing timezone")
        return parsed

    result = (timestamp(record["completed_at"]) - timestamp(record["created_at"])).total_seconds()
    if result < 0:
        raise ValueError("Completed before creation")
    return result


def reconcile(base: str, ids: list[str], timeout: int = 300) -> dict:
    if base not in ALLOWED_BASES or not 1 <= timeout <= 600:
        raise ValueError("Unsafe endpoint or timeout")
    if not 1 <= len(ids) <= 120 or len(set(ids)) != len(ids):
        raise ValueError("A bounded, distinct exact job set is required")
    if any(str(UUID(value)) != value for value in ids):
        raise ValueError("Canonical job UUIDs required")
    remaining = set(ids)
    complete = {}
    errors = []
    deadline = time.monotonic() + timeout
    while remaining and time.monotonic() < deadline:
        for job_id in list(remaining):
            try:
                record = get_job(base, job_id)
            except (HTTPError, URLError, TimeoutError, OSError) as exc:
                errors.append({"job_id": job_id, "error": type(exc).__name__})
                continue
            state = record.get("status")
            if state == "failed":
                raise ValueError(f"Job {job_id} failed")
            if state not in ("queued", "processing", "completed"):
                raise ValueError(f"Unknown status for {job_id}")
            if state == "completed":
                if type(record.get("attempts")) is not int or record["attempts"] < 1:
                    raise ValueError("Invalid job attempts")
                duration_seconds(record)
                complete[job_id] = record
                remaining.remove(job_id)
        if remaining:
            time.sleep(2)
    if remaining:
        raise ValueError(f"Timed out with {len(remaining)} of {len(ids)} jobs incomplete")
    durations = [duration_seconds(row) for row in complete.values()]
    return {
        "passed": True,
        "expected": len(ids),
        "completed": len(complete),
        "retries_observed": sum(row["attempts"] - 1 for row in complete.values()),
        "latency_seconds_p50": percentile_nearest_rank(durations, 50),
        "latency_seconds_p95": percentile_nearest_rank(durations, 95),
        "transient_read_errors": errors,
        "job_ids": ids,
        "jobs": list(complete.values()),
        "limitations": (
            "Durable terminal-state verification, not an exactly-once execution guarantee"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipts", type=Path, required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--base", default="http://127.0.0.1:18088")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.base not in ALLOWED_BASES:
        parser.error("Target is not the pinned local k3d port-forward")
    if args.timeout < 1 or args.timeout > 600:
        parser.error("Timeout must be between 1 and 600 seconds")
    ids = parse_receipts(args.receipts, args.run_id, args.expected_count)
    try:
        report = reconcile(args.base, ids, args.timeout)
    except (ValueError, OSError) as exc:
        report = {
            "passed": False,
            "error": str(exc),
            "expected": len(ids),
            "job_ids": ids,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k != "job_ids"}, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
