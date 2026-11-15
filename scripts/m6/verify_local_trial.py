"""Independent process: fresh read-only verification after local fault cleanup.

No Kubernetes mutation, action approval or model call is performed here.
"""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from uuid import UUID, uuid4

from opsproof_control.m6_verification import VerificationReceipt

from scripts.m6.independent_hypothesis import establish
from scripts.m6.local_environment import (
    ROOT,
    LocalEnvironment,
    fresh_database_probe,
    http,
    source_identity,
    utc,
    write_json,
)
from scripts.m6.process_identity import running
from scripts.m6.scenario_adapters import ADAPTERS
from scripts.m6.trial_evidence import (
    durable_inventory,
    durable_jobs,
    prometheus,
    telemetry,
)


def verify(env, state, *, cleanup_only=False, run_directory=None):
    if state["scenario"] not in ADAPTERS:
        raise ValueError("Unknown fixed scenario")
    directory = run_directory or env.output.parent
    observer_dir = directory / "observer"
    samples = []
    if cleanup_only:
        identity = {"observer_id": str(uuid4())}
    else:
        source = json.loads((directory / "source.json").read_text(encoding="utf-8"))
        if source_identity()["tree_sha256"] != source["tree_sha256"]:
            raise ValueError("Source changed during the trial; evidence cannot authorize success")
        identity = json.loads((observer_dir / "identity.json").read_text(encoding="utf-8"))
        finished = json.loads((observer_dir / "finished.json").read_text(encoding="utf-8"))
        if (
            identity["trial_id"] != state["trial_id"]
            or identity["target_uid"] != state["target_uid"]
            or finished["observer_id"] != identity["observer_id"]
            or datetime.fromisoformat(identity["started_at"])
            > datetime.fromisoformat(state["dispatch_intent_at"])
        ):
            raise ValueError("Independent observer identity does not match this dispatch")
        raw = (observer_dir / "samples.jsonl").read_bytes()
        if len(raw) > 10_000_000:
            raise ValueError("Observer sample bound exceeded")
        samples = [json.loads(line) for line in raw.decode("utf-8").splitlines()]
    baseline = env.baseline()
    current_target = env.get(*ADAPTERS[state["scenario"]].target_resource)
    if current_target["metadata"]["uid"] != state["target_uid"]:
        raise ValueError("Original target resource identity was replaced")
    if len(state["submitted_keys"]) != len(state["job_ids"]):
        raise ValueError(
            "Lost submission receipts require explicit key reconciliation before release"
        )
    jobs = durable_jobs(env, state["job_ids"])
    ids = {row["id"] for row in jobs}
    if ids != set(state["job_ids"]) or any(row["status"] != "completed" for row in jobs):
        raise ValueError("PostgreSQL exact-job identity/terminal state mismatch")
    if {row["idempotency_key"] for row in jobs} != set(state["submitted_keys"]):
        raise ValueError("Durable job submission keys do not match the recorded intents")
    for row in jobs:
        timestamps = [
            datetime.fromisoformat(row[key]) for key in ("created_at", "started_at", "completed_at")
        ]
        if any(value.tzinfo is None for value in timestamps) or timestamps != sorted(timestamps):
            raise ValueError("Durable job timestamps are missing timezone or out of order")
        code, remote = http(18088, "/api/v1/jobs/" + row["id"])
        if (
            code != 200
            or remote["id"] != row["id"]
            or remote["status"] != row["status"]
            or remote["attempts"] != row["attempts"]
            or remote["duration_ms"] != row["duration_ms"]
        ):
            raise ValueError("Independent PostgreSQL/API job reconciliation failed")
    inventory = durable_inventory(env, state["inventory_cutoff"])
    if inventory != state["inventory_before"]:
        raise ValueError("Pre-existing durable job identity inventory changed")
    worker = env.get("deployment", "demo-worker")
    if worker["spec"]["template"]["spec"]["containers"][0]["image"] != state["worker_image"]:
        raise ValueError("Worker image changed unexpectedly")
    scenario = state["scenario"]
    if state.get("capacity_mode"):
        if running(state["load_process_pid"]):
            raise ValueError("Owned capacity generator was not stopped")
        app = env.get("application", "demo", "argocd")
        original = state["original_application"]
        if app["spec"]["source"]["helm"]["parameters"] != original["spec"]["source"]["helm"][
            "parameters"
        ] or app["spec"].get("ignoreDifferences", []) != original["spec"].get(
            "ignoreDifferences", []
        ):
            raise ValueError("Capacity configuration/ignore rules not restored")
        if any(row["attempts"] != 1 for row in jobs):
            raise ValueError("Capacity comparison contains retried work")
    if scenario == "database_connectivity":
        policy = env.get("networkpolicy", "opsproof-namespace-traffic")
        if (
            policy["metadata"]["uid"] != state["policy"]["metadata"]["uid"]
            or policy["spec"] != state["policy"]["spec"]
        ):
            raise ValueError("Original NetworkPolicy was not restored")
        code, probe = fresh_database_probe()
        if code != 200 or not probe or probe.get("ready") is not True:
            raise ValueError("Fresh database connectivity was not restored")
    if scenario in ("faulty_release", "downstream_latency"):
        application = env.get("application", "demo", "argocd")
        if (
            application["spec"]["source"]["helm"]["parameters"]
            != state["original_application"]["spec"]["source"]["helm"]["parameters"]
        ):
            raise ValueError("Original GitOps configuration was not restored")
    if scenario == "faulty_release":
        rollout = env.get("rollout", "demo-api")
        if rollout["spec"]["template"]["spec"]["containers"][0]["image"] != state["stable_image"]:
            raise ValueError("Stable release image changed")
        route = env.get("httproute", "demo-release")
        weights = {
            item["name"]: item.get("weight", 1) for item in route["spec"]["rules"][0]["backendRefs"]
        }
        if weights.get("demo-api") != 100 or weights.get("demo-api-canary") != 0:
            raise ValueError("Stable traffic route not restored")
    if scenario == "worker_failure" and not cleanup_only:
        pods = env.get("pods")["items"]
        if any(p["metadata"]["uid"] == state["old_worker"]["uid"] for p in pods):
            raise ValueError("Terminated worker still present")
    current = prometheus(env)
    # Trace identities come from the independent observer's actual requests.
    state = {
        **state,
        "failed_trace_ids": [r["trace_id"] for r in samples if r.get("release_status") == 500],
    }
    signals = telemetry(env, state) if not cleanup_only else {}
    if not current["fresh"]:
        raise ValueError("Current Prometheus freshness not established")
    # Hypothesis requirements belong to establish(). A restored workload with
    # insufficient fault evidence can be verified clean and recorded failed.
    hypothesis = establish(state, samples, jobs, signals) if not cleanup_only else False
    if cleanup_only:
        raw = json.dumps(
            {
                "baseline": baseline,
                "jobs": jobs,
                "inventory": inventory,
                "prometheus": current,
            },
            sort_keys=True,
        ).encode()
    cleanup_checks = {
        "current_health": True,
        "exact_jobs": True,
        "original_configuration": True,
        "observer_identity": True,
    }
    receipt = VerificationReceipt(
        trial_id=UUID(state["trial_id"]),
        dispatch_id=UUID(state["dispatch_id"]),
        observer_id=UUID(identity["observer_id"]),
        target_uid=state["target_uid"],
        verified_at=datetime.fromisoformat(utc()),
        observer_sha256=hashlib.sha256(raw).hexdigest(),
        cleanup_verified=True,
        hypothesis_verified=hypothesis,
        checks=cleanup_checks,
    )
    return {
        "verified_at": utc(),
        "cleanup_verified": True,
        "hypothesis_verified": hypothesis,
        "verification_receipt": receipt.model_dump(mode="json"),
        "baseline": baseline,
        "durable_jobs": jobs,
        "inventory": inventory,
        "prometheus": current,
        "telemetry": signals,
        "verifier_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--cleanup-only", action="store_true")
    parser.add_argument("--reconciliation-directory", type=Path)
    args = parser.parse_args()
    directory = args.run_directory.resolve(strict=True)
    if args.run_directory.is_symlink() or not directory.is_relative_to(ROOT / ".runtime/m6/trials"):
        parser.error("Only canonical M6 trial evidence directories are accepted")
    work = directory
    if args.reconciliation_directory:
        work = args.reconciliation_directory.resolve(strict=True)
        if (
            not args.cleanup_only
            or args.reconciliation_directory.is_symlink()
            or work.parent != directory
        ):
            parser.error("Only an owned trial reconciliation directory is accepted")
    state = json.loads(
        (work / ("state.json" if args.cleanup_only else "adapter-final.json")).read_text(
            encoding="utf-8"
        )
    )
    output = work / "independent"
    output.mkdir(exist_ok=False)
    env = LocalEnvironment(output, read_only=True)
    targets = ["demo", "control", "prometheus", "loki", "tempo"]
    if state["scenario"] == "faulty_release":
        targets.append("release")
    report = {"cleanup_verified": False, "hypothesis_verified": False}
    try:
        with env.forwarded(targets):
            report = verify(env, state, cleanup_only=args.cleanup_only, run_directory=directory)
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        report["reason"] = str(exc)[:300]
    write_json(work / "independent-result.json", report)
    return 0 if report["cleanup_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
