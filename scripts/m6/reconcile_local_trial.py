"""Explicit cleanup-only reconciliation after interruption. Never replays injection."""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from urllib.parse import quote
from uuid import UUID, uuid4

import psycopg
from opsproof_control import m6_trial_store as store
from psycopg.rows import dict_row

from scripts.m5.render_local_secrets import read_env
from scripts.m6.capacity_adapter import Capacity
from scripts.m6.live_observer import child_environment
from scripts.m6.local_environment import ROOT, LocalEnvironment, utc, write_json
from scripts.m6.restricted_access import RestrictedAccess
from scripts.m6.run_k6_local import local_prefix
from scripts.m6.scenario_adapters import ADAPTERS
from scripts.m6.trial_evidence import reconcile_submission_keys


def load_checkpoint(directory):
    candidates = [directory / "adapter-final.json"]
    candidates += sorted(directory.glob("*-adapter-state.json"), reverse=True)
    for path in candidates:
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= 2_000_000:
            value = json.loads(path.read_text(encoding="utf-8"))
            return value["data"] if "data" in value else value
    raise ValueError("No trustworthy original-state checkpoint; manual review required")


def execute(directory, acknowledgment):
    if acknowledgment != "M6_RECONCILE_ONLY":
        raise ValueError("Explicit cleanup-only acknowledgment required")
    if directory.is_symlink():
        raise ValueError("Linked trial directories are not accepted")
    directory = directory.resolve(strict=True)
    if directory.parent != ROOT / ".runtime/m6/trials":
        raise ValueError("Exact local M6 run directory required")
    state = load_checkpoint(directory)
    output = directory / ("reconcile-" + uuid4().hex)
    output.mkdir()
    result = {
        "started_at": utc(),
        "cleanup_verified": False,
        "injection_replayed": False,
    }
    env = LocalEnvironment(output)
    try:
        with env.forwarded(["demo_db", "demo_redis", "demo", "control", "prometheus", "ledger"]):
            with RestrictedAccess(
                output,
                state["scenario"],
                state.get("capacity_mode"),
                cleanup_only=True,
                original_state=state,
            ) as access:
                env.kube = local_prefix(access.configs["actuate"])
                values = read_env(ROOT / ".env")
                dsn = (
                    "postgresql://opsproof:"
                    + quote(values["OPSPROOF_CONTROL_DB_PASSWORD"], safe="")
                    + "@127.0.0.1:18032/opsproof"
                )
                trial = UUID(state["trial_id"])

                def connection():
                    return psycopg.connect(dsn, row_factory=dict_row, connect_timeout=3)

                with connection() as conn:
                    row = store.get_trial(conn, trial)
                    lease = conn.execute(
                        "SELECT fence_token FROM m6_target_leases WHERE trial_id=%s",
                        (trial,),
                    ).fetchone()
                    if (
                        not lease
                        or not row.get("dispatch_intent_at")
                        or row["target_uid"] != state["target_uid"]
                    ):
                        raise ValueError("Original dispatch/reservation identity unavailable")
                    token = lease["fence_token"]
                    state.update(
                        dispatch_id=str(row["dispatch_id"]),
                        dispatch_intent_at=row["dispatch_intent_at"].isoformat(),
                    )
                    if row["phase"] != "indeterminate":
                        store.mark_uncertain(
                            conn,
                            trial,
                            fence_token=token,
                            reason="Explicit reconciliation of interrupted executor",
                        )
                adapter = (
                    Capacity(env, state["capacity_mode"])
                    if state.get("capacity_mode")
                    else ADAPTERS[state["scenario"]](env)
                )
                adapter.state = state
                if state.get("capacity_mode") and (ROOT / state["capacity_log_path"]).is_file():
                    adapter.load_logs()
                reconcile_submission_keys(env, state)
                # Cleanup only. There is deliberately no call to inject/observe.
                adapter.cleanup()
                write_json(output / "state.json", state)
                access.refresh_forward_permissions()
                # Close only these forwards before the separate verifier owns them.
                for target in ("demo", "control", "prometheus"):
                    env.stop_forward(target)
                with (output / "verifier.log").open("x", encoding="utf-8") as log:
                    run = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "scripts.m6.verify_local_trial",
                            "--run-directory",
                            str(directory),
                            "--cleanup-only",
                            "--reconciliation-directory",
                            str(output),
                        ],
                        cwd=ROOT,
                        env=child_environment(access),
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        timeout=180,
                        check=False,
                    )
                proof_path = output / "independent-result.json"
                proof = json.loads(proof_path.read_text(encoding="utf-8"))
                if run.returncode or proof.get("cleanup_verified") is not True:
                    raise RuntimeError(
                        "Independent cleanup verification failed; reservation retained"
                    )
                access.close()
                ref = {
                    "relative_path": proof_path.relative_to(ROOT).as_posix(),
                    "sha256": hashlib.sha256(proof_path.read_bytes()).hexdigest(),
                }
                cleanup_ref = env.save(
                    "verified-cleanup",
                    {
                        "independent_result": ref,
                        "cleanup_verified": True,
                        "restricted_access_removed": True,
                    },
                )
                with connection() as conn:
                    store.record_verification(
                        conn,
                        trial,
                        fence_token=token,
                        report_json=json.dumps(proof["verification_receipt"]),
                        **ref,
                    )
                    store.attach_artifact(
                        conn, trial, fence_token=token, kind="cleanup", **cleanup_ref
                    )
                    store.resolve_uncertain(
                        conn,
                        trial,
                        fence_token=token,
                        reason=(
                            "Fresh independent cleanup verified after process interruption; "
                            "original outcome retained"
                        ),
                    )
                result.update(
                    cleanup_verified=True,
                    original_outcome="INDETERMINATE",
                    reservation_released=True,
                )
    except Exception as exc:
        result["error_type"] = type(exc).__name__
    result["ended_at"] = utc()
    write_json(output / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-directory", type=Path, required=True)
    parser.add_argument("--acknowledge", required=True)
    args = parser.parse_args()
    result = execute(args.run_directory, args.acknowledge)
    print(json.dumps(result, indent=2))
    return 0 if result["cleanup_verified"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
