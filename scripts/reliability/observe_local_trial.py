"""Separate live observer. Never performs a Kubernetes or application mutation.

The executor's success flags are not inputs. Missing samples remain unknown.
This is independent process evidence on a trusted local host, not protection
against a malicious host administrator.
"""

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from uuid import uuid4

from scripts.reliability.local_environment import (
    ROOT,
    LocalEnvironment,
    fresh_database_probe,
    http,
    utc,
    write_json,
)


def sample(env, scenario):
    result = {"at": utc(), "errors": []}
    for key, port in (("demo_ready", 18088), ("control_ready", 18090)):
        result[key + "_at"] = utc()
        try:
            result[key] = http(port, "/health/ready", timeout=1)[0]
        except OSError, TimeoutError:
            result[key] = None
        result[key + "_until"] = utc()
    if scenario == "database_connectivity":
        result["database_probe_at"] = utc()
        try:
            code, probe = fresh_database_probe()
            result["database_probe_status"] = code
            result["database_probe_detail"] = probe.get("detail") if probe else None
        except OSError, TimeoutError:
            result["database_probe_status"] = None
        result["database_probe_until"] = utc()
    try:
        result["stats"] = http(18088, "/api/v1/stats", timeout=1)[1]
    except OSError, TimeoutError:
        result["stats"] = None
    try:
        result["queue"] = env.queue()
        worker = env.get("deployment", "demo-worker")
        result["worker"] = {
            "uid": worker["metadata"]["uid"],
            "desired": worker["spec"].get("replicas"),
            "available": worker.get("status", {}).get("availableReplicas", 0),
        }
        pods = env.get("pods")["items"]
        result["worker_pods"] = [
            {
                "uid": p["metadata"]["uid"],
                "name": p["metadata"]["name"],
                "phase": p["status"].get("phase"),
                "ready": all(c.get("ready") for c in p["status"].get("containerStatuses", [{}])),
            }
            for p in pods
            if p["metadata"].get("labels", {}).get("opsproof.io/role") == "worker"
        ]
        rollout = env.get("rollout", "demo-api")
        result["rollout"] = {
            "uid": rollout["metadata"]["uid"],
            "desired": rollout["spec"].get("replicas"),
            "available": rollout.get("status", {}).get("availableReplicas", 0),
            "abort": rollout.get("status", {}).get("abort", False),
            "phase": rollout.get("status", {}).get("phase"),
        }
        if scenario == "faulty_release":
            trace_id = uuid4().hex
            result["release_status"] = http(
                18081,
                "/api/v1/stats",
                timeout=2,
                headers={"traceparent": f"00-{trace_id}-{uuid4().hex[:16]}-01"},
            )[0]
            result["trace_id"] = trace_id
            result["analyses"] = [
                {
                    "uid": a["metadata"]["uid"],
                    "owners": a["metadata"].get("ownerReferences", []),
                    "created_at": a["metadata"]["creationTimestamp"],
                    "phase": a.get("status", {}).get("phase"),
                }
                for a in env.get("analysisruns")["items"]
            ]
        if scenario == "misleading_evidence":
            try:
                result["observer_metrics_status"] = http(19090, "/-/ready", timeout=1)[0]
            except OSError, TimeoutError:
                result["observer_metrics_status"] = None
    except Exception as exc:
        result["errors"].append(type(exc).__name__)
    result["collected_until"] = utc()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    args = parser.parse_args()
    directory = args.run_directory.resolve(strict=True)
    if args.run_directory.is_symlink() or not directory.is_relative_to(
        ROOT / ".runtime/reliability/trials"
    ):
        parser.error("Canonical local M6 trial directory required")
    request = json.loads((directory / "observer-request.json").read_text(encoding="utf-8"))
    output = directory / "observer"
    output.mkdir(exist_ok=False)
    env = LocalEnvironment(output, read_only=True)
    identity = {
        "observer_id": str(uuid4()),
        "trial_id": request["trial_id"],
        "target_uid": request["target_uid"],
        "started_at": utc(),
        "source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    # A ready file is written only after an actual independent sample.
    deadline = time.monotonic() + 600
    with (output / "samples.jsonl").open("x", encoding="utf-8") as stream:
        while time.monotonic() < deadline:
            row = sample(env, request["scenario"])
            stream.write(json.dumps(row, allow_nan=False) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
            if not (output / "identity.json").exists() and (
                row.get("demo_ready") == row.get("control_ready") == 200
                and not row["errors"]
                and row.get("queue", {}).get("lag") == 0
            ):
                write_json(output / "identity.json", identity)
            if (directory / "observer-stop").exists():
                break
            time.sleep(0.5)
    write_json(output / "finished.json", {**identity, "ended_at": utc()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
