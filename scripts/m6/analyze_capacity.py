"""Analyze repeatable M5 capacity records without cherry-picking or fake precision.

Require >=3 independent, passed, equivalent workloads per configuration.
No statistical significance is inferred from three runs; report medians/ranges.
"""

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

MODES = ("fixed", "hpa", "keda")
MEASURES = ("job_p50_seconds", "job_p95_seconds", "jobs_per_second", "http_p95_ms")
WORKLOAD_KEYS = ("count", "duration_ms", "load_seconds", "target_requests_per_second")


def validate_trial(record: dict, mode: str) -> tuple[dict, tuple]:
    if record.get("mode") != mode or record.get("passed") is not True or record.get("failure"):
        raise ValueError("Failed/mislabeled trial must not enter success comparison")
    workload = record.get("workload")
    if not isinstance(workload, dict):
        raise ValueError("Missing workload results")
    signature = tuple(workload.get(k) for k in WORKLOAD_KEYS)
    if any(not isinstance(value, int) or value <= 0 for value in signature):
        raise ValueError("Incomplete workload parameters")
    if workload.get("http_failures") != 0:
        raise ValueError("HTTP failures; not a successful comparison trial")
    if not isinstance(workload.get("jobs"), list) or len(workload["jobs"]) != workload["count"]:
        raise ValueError("Exact job list missing")
    ids = [job.get("id") for job in workload["jobs"]]
    if any(not id_ for id_ in ids) or len(set(ids)) != len(ids):
        raise ValueError("Duplicate or missing durable job IDs")
    if any(job.get("status") != "completed" or job.get("attempts") != 1
           for job in workload["jobs"]):
        raise ValueError("Unexpected job state/retries")
    for measure in MEASURES:
        value = workload.get(measure)
        if type(value) not in (int, float) or not 0 < value < 1_000_000:
            raise ValueError(f"Missing or invalid {measure}")
    if (
        not isinstance(record.get("application_revision"), str)
        or not record["application_revision"]
    ):
        raise ValueError("Actual deployed Git revision missing")
    script_hash = record.get("load_script_sha256")
    if not isinstance(script_hash, str) or len(script_hash) != 64:
        raise ValueError("Missing script identity")
    return workload, (signature, record["application_revision"], script_hash)


def analyze(grouped: dict[str, list[dict]], minimum_trials: int = 3) -> dict:
    if not 3 <= minimum_trials <= 20:
        raise ValueError("Trials gate outside allowed range")
    if set(grouped) != set(MODES):
        raise ValueError("Fixed, HPA and KEDA modes all required")
    identity = None
    unique_timestamps = set()
    output = {"trial_gate": minimum_trials, "modes": {}, "limitations": [
        "Local controlled trials only; not a production SLO or statistical significance claim",
        "HPA scales the API and KEDA scales workers; they address different bottlenecks",
    ]}
    for mode in MODES:
        records = grouped[mode]
        if len(records) < minimum_trials:
            raise ValueError(f"Only {len(records)} {mode} trials; need {minimum_trials}")
        numbers = defaultdict(list)
        for record in records:
            workload, trial_identity = validate_trial(record, mode)
            if identity is None:
                identity = trial_identity
            if identity != trial_identity:
                raise ValueError("Mixed workload/source revisions are not comparable")
            timestamp = record.get("timestamp_utc")
            if not timestamp or (mode, timestamp) in unique_timestamps:
                raise ValueError("Missing/duplicated trial timestamp")
            unique_timestamps.add((mode, timestamp))
            for key in MEASURES:
                numbers[key].append(float(workload[key]))
        output["modes"][mode] = {
            "trials": len(records),
            "measurements": {
                key: {
                    "median": statistics.median(values),
                    "min": min(values),
                    "max": max(values),
                    "raw": values,
                }
                for key, values in numbers.items()
            },
        }
    output["source_identity"] = {
        "workload": dict(zip(WORKLOAD_KEYS, identity[0], strict=True)),
        "application_revision": identity[1],
        "load_script_sha256": identity[2],
    }
    fixed_p95 = output["modes"]["fixed"]["measurements"]["job_p95_seconds"]["median"]
    keda_p95 = output["modes"]["keda"]["measurements"]["job_p95_seconds"]["median"]
    output["keda_vs_fixed_p95_reduction_percent"] = round(
        (fixed_p95 - keda_p95) / fixed_p95 * 100, 3
    )
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trial", action="append", required=True, metavar="MODE:PATH")
    parser.add_argument("--minimum-trials", type=int, default=3)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    groups = defaultdict(list)
    for source in args.trial:
        mode, sep, path = source.partition(":")
        if sep != ":" or mode not in MODES:
            parser.error("Expected fixed:path, hpa:path or keda:path")
        groups[mode].append(json.loads(Path(path).read_text(encoding="utf-8")))
    report = analyze(groups, args.minimum_trials)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"trials": {m: report["modes"][m]["trials"] for m in MODES},
                      "keda_vs_fixed_p95_reduction_percent": (
                          report["keda_vs_fixed_p95_reduction_percent"]
                      )}, indent=2))


if __name__ == "__main__":
    main()
