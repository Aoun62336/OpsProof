"""Explicit, host-side local executor with durable pre-send intent and cleanup.

Never called by API routes, CI or recovery workers. No default enable flag,
cloud context, arbitrary commands, model calls or automatic schema migration.
"""

import argparse
import hashlib
import json
import subprocess
import sys
import traceback
from contextlib import ExitStack, nullcontext
from urllib.parse import quote
from uuid import uuid4

import psycopg
from opsproof_control import trial_store as store
from opsproof_control.trial_catalog import Scenario
from opsproof_control.trial_state import TrialPhase
from psycopg.rows import dict_row

from scripts.platform.render_local_secrets import read_env
from scripts.reliability.live_observer import LiveObserver, child_environment
from scripts.reliability.local_environment import (
    ROOT,
    LocalEnvironment,
    resource_preflight,
    source_identity,
    utc,
    write_json,
)
from scripts.reliability.restricted_access import RestrictedAccess
from scripts.reliability.run_k6_local import local_prefix
from scripts.reliability.scenario_adapters import ADAPTERS
from scripts.reliability.trial_evidence import durable_inventory


def execute(scenario, acknowledgment, capacity_mode=None):
    if acknowledgment != "M6_LOCAL_FAULT_TRIAL":
        raise ValueError("Explicit local trial acknowledgment required")
    if scenario not in ADAPTERS:
        raise ValueError("Scenario outside fixed six-scenario catalog")
    run_id = "m6-" + uuid4().hex
    directory = ROOT / ".runtime/m6/trials" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    result = {
        "run_id": run_id,
        "scenario": scenario,
        "started_at": utc(),
        "status": "BLOCKED",
        "fault_sent": False,
        "cleanup_verified": False,
    }
    resources = resource_preflight()
    write_json(directory / "resources.json", resources)
    write_json(directory / "source.json", source_identity())
    if not resources["passed"]:
        result["blockers"] = resources["blockers"]
        write_json(directory / "result.json", result)
        return result
    env = LocalEnvironment(directory)
    if capacity_mode is not None:
        if scenario != "worker_saturation":
            raise ValueError("Capacity modes apply only to worker saturation")
        from scripts.reliability.capacity_adapter import Capacity

        adapter = Capacity(env, capacity_mode)
    else:
        adapter = ADAPTERS[scenario](env)
    dsn = None
    trial_id = token = None
    injection_error = cleanup_error = None
    references = {}
    resources_stack = ExitStack()
    observer = None

    def connection():
        return psycopg.connect(dsn, row_factory=dict_row, connect_timeout=3)

    def attach(kind, ref):
        with connection() as conn:
            store.attach_artifact(conn, trial_id, fence_token=token, kind=kind, **ref)

    targets = ["demo", "control", "prometheus"]
    if scenario == "faulty_release":
        targets.append("release")
    try:
        resources_stack.enter_context(env.forwarded(["demo_db", "demo_redis", "ledger"]))
        access = resources_stack.enter_context(RestrictedAccess(directory, scenario, capacity_mode))
        env.kube = local_prefix(access.configs["actuate"])
        with env.forwarded(targets):
            values = read_env(ROOT / ".env")
            dsn = (
                "postgresql://opsproof:"
                + quote(values["OPSPROOF_CONTROL_DB_PASSWORD"], safe="")
                + "@127.0.0.1:18032/opsproof"
            )
            with connection() as conn:
                version = conn.execute("SELECT version_num FROM alembic_version").fetchone()
                if version["version_num"] != "0007":
                    raise RuntimeError(
                        "Controlled local migration/deployment through 0007 is a prerequisite"
                    )
            baseline = env.baseline()
            state = adapter.snapshot()
            state["inventory_cutoff"] = utc()
            state["inventory_before"] = durable_inventory(env, state["inventory_cutoff"])
            source = source_identity()
            with connection() as conn:
                row, _ = store.create_trial(
                    conn,
                    request_key=run_id,
                    scenario=Scenario(scenario),
                    source_revision=source["head"],
                )
                trial_id = row["id"]
            result["trial_id"] = str(trial_id)
            state["trial_id"] = str(trial_id)
            # Claim only this requested trial; the source worker may already
            # have advanced it. Neither path substitutes for actual baseline.
            with connection() as conn:
                row = store._locked(conn, trial_id)
                if row["phase"] == "requested":
                    store._move(conn, row, TrialPhase.PREFLIGHT)
                    conn.execute(
                        "UPDATE m6_trial_outbox SET dispatched_at=now() WHERE trial_id=%s "
                        "AND event_type='preflight_requested'",
                        (trial_id,),
                    )
                store._audit(
                    conn,
                    trial_id,
                    "live_local_preflight_observed",
                    {
                        "baseline": baseline,
                        "tree_sha256": source["tree_sha256"],
                        "dirty": source["dirty"],
                    },
                )
                store.arm_trial(
                    conn,
                    trial_id,
                    approved_scope=True,
                    cleanup_confirmed=True,
                    confirmation="ARM M6 LOCAL TRIAL",
                )
                token = conn.execute(
                    "SELECT fence_token FROM m6_target_leases WHERE trial_id=%s",
                    (trial_id,),
                ).fetchone()["fence_token"]
            references["preflight"] = env.save(
                "preflight", {"baseline": baseline, "adapter": state}
            )
            attach("preflight", references["preflight"])
            adapter.checkpoint()
            observer = LiveObserver(directory, access, state)
            resources_stack.callback(observer.stop)
            current_target = env.get(*adapter.target_resource)
            if (
                current_target["metadata"]["uid"] != state["target_uid"]
                or current_target["metadata"]["resourceVersion"] != state["target_version"]
            ):
                raise RuntimeError(
                    "Target identity/version changed after preflight; no fault dispatched"
                )
            with connection() as conn:
                dispatch = store.begin_dispatch(
                    conn,
                    trial_id,
                    fence_token=token,
                    target_uid=state["target_uid"],
                    target_version=state["target_version"],
                    maximum_seconds=600,
                )
            # The transaction above has committed. No mutation may precede it.
            result["dispatch_id"] = str(dispatch)
            state["dispatch_id"] = str(dispatch)
            with connection() as conn:
                dispatched = store.get_trial(conn, trial_id)
                state["dispatch_intent_at"] = dispatched["dispatch_intent_at"].isoformat()
            adapter.checkpoint()
            result["status"] = "RUNNING"

            def authorization_guard():
                with connection() as conn:
                    current = store.get_trial(conn, trial_id)
                    if current["abort_requested"] or current["phase"] not in (
                        "armed",
                        "injected",
                        "observing",
                        "recovering",
                        "verifying",
                    ):
                        raise RuntimeError("Durable trial aborted or execution ownership lost")

            env.authorization_guard = authorization_guard
            try:
                result["fault_sent"] = None  # A lost acknowledgment is unknown, not False.
                result["mutation_attempted"] = True
                receipt = adapter.inject()
                result["fault_sent"] = True
                references["injection"] = env.save("injection-receipt", receipt)
                with connection() as conn:
                    store.acknowledge_injection(
                        conn,
                        trial_id,
                        fence_token=token,
                        dispatch_id=dispatch,
                        receipt_path=references["injection"]["relative_path"],
                        receipt_sha256=references["injection"]["sha256"],
                    )
                    store.progress(
                        conn,
                        trial_id,
                        fence_token=token,
                        next_phase=TrialPhase.OBSERVING,
                    )
                observations = adapter.observe()
                references["observation"] = env.save("scenario-observation", observations)
                attach("metric", references["observation"])
            except Exception as exc:
                injection_error = type(exc).__name__ + ": " + str(exc)[:180]
                env.save(
                    "execution-error",
                    {"error": injection_error, "outcome_may_be_unknown": True},
                )
            finally:
                # Stop guards cannot prevent neutralizing an already sent fault.
                env.authorization_guard = None
                state["cleanup_started_at"] = utc()
                adapter.checkpoint()
                try:
                    restored = adapter.cleanup()
                    references["cleanup_attempt"] = env.save("cleanup-attempt", restored)
                except Exception as exc:
                    cleanup_error = type(exc).__name__ + ": " + str(exc)[:180]
                    env.save("cleanup-error", {"error": cleanup_error})
                write_json(directory / "adapter-final.json", adapter.state)
                observer.stop()
                with connection() as conn:
                    row = store.get_trial(conn, trial_id)
                    if row["phase"] in (
                        "armed",
                        "injected",
                        "observing",
                        "recovering",
                        "verifying",
                    ):
                        if injection_error or cleanup_error:
                            store.mark_uncertain(
                                conn,
                                trial_id,
                                fence_token=token,
                                reason=injection_error or cleanup_error,
                            )
                        elif row["phase"] == "observing":
                            store.progress(
                                conn,
                                trial_id,
                                fence_token=token,
                                next_phase=TrialPhase.VERIFYING,
                            )
        # All executor forwards are closed before the independent process owns
        # its own fresh observer connections. The ledger forward is recreated
        # separately only after verification has ended.
        access.refresh_forward_permissions()
        with (directory / "independent-process.log").open("x", encoding="utf-8") as log:
            check = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "scripts.reliability.verify_local_trial",
                    "--run-directory",
                    str(directory),
                ],
                cwd=ROOT,
                env=child_environment(access),
                stdout=log,
                stderr=subprocess.STDOUT,
                timeout=180,
                check=False,
            )
        proof = json.loads((directory / "independent-result.json").read_text(encoding="utf-8"))
        result["cleanup_verified"] = check.returncode == 0 and proof.get("cleanup_verified") is True
        ref = {
            "relative_path": (directory / "independent-result.json").relative_to(ROOT).as_posix(),
            "sha256": hashlib.sha256(
                (directory / "independent-result.json").read_bytes()
            ).hexdigest(),
        }
        # Revoke the short-lived execution/observer credentials before releasing
        # any trial reservation or recording success. The bootstrap-owned ledger
        # forward stays available solely to finish the durable bookkeeping.
        try:
            access.close()
        except Exception:
            result["access_cleanup_failed"] = True
            raise
        with nullcontext():
            if result["cleanup_verified"]:
                with connection() as conn:
                    store.record_verification(
                        conn,
                        trial_id,
                        fence_token=token,
                        report_json=json.dumps(proof["verification_receipt"]),
                        **ref,
                    )
                cleanup_ref = env.save(
                    "verified-cleanup",
                    {
                        "independent_result": ref,
                        "cleanup_verified": True,
                        "restricted_access_removed": True,
                    },
                )
                with connection() as conn:
                    store.attach_artifact(
                        conn,
                        trial_id,
                        fence_token=token,
                        kind="cleanup",
                        **cleanup_ref,
                        observations={
                            key: proof[key]
                            for key in (
                                "durable_jobs",
                                "prometheus",
                                "telemetry",
                                "baseline",
                                "hypothesis_verified",
                                "cleanup_verified",
                            )
                        },
                    )
            with connection() as conn:
                row = store.get_trial(conn, trial_id)
                if result["cleanup_verified"] and row["phase"] == "indeterminate":
                    store.resolve_uncertain(
                        conn,
                        trial_id,
                        fence_token=token,
                        reason="Independent process verified restoration after uncertainty",
                    )
                elif result["cleanup_verified"] and proof["hypothesis_verified"]:
                    store.verified_complete(
                        conn,
                        trial_id,
                        fence_token=token,
                        independently_verified=True,
                        cleanup_verified=True,
                    )
                elif result["cleanup_verified"]:
                    store.verified_failure(
                        conn,
                        trial_id,
                        fence_token=token,
                        cleanup_verified=True,
                        reason="Scenario hypothesis not independently established",
                    )
                elif row["phase"] != "indeterminate":
                    store.mark_uncertain(
                        conn,
                        trial_id,
                        fence_token=token,
                        reason="Independent cleanup/evidence gates failed; reservation retained",
                    )
                result["status"] = store.get_trial(conn, trial_id)["phase"].upper()
    except (Exception, KeyboardInterrupt) as exc:
        result["error_type"] = type(exc).__name__
        write_json(
            directory / "executor-diagnostic.json",
            {
                "error_type": type(exc).__name__,
                "errno": getattr(exc, "errno", None),
                "winerror": getattr(exc, "winerror", None),
                "frames": [
                    {"file": frame.filename, "line": frame.lineno, "function": frame.name}
                    for frame in traceback.extract_tb(exc.__traceback__)
                ],
            },
        )
        # Never persist arbitrary DB/provider exception text containing DSNs.
        result["reason"] = "Local prerequisite or execution failed; inspect bounded local artifacts"
        if trial_id is not None:
            result["status"] = "INDETERMINATE"
        if trial_id is not None and token is not None and dsn is not None:
            try:
                with connection() as conn:
                    row = store.get_trial(conn, trial_id)
                    if row.get("dispatch_intent_at") and row["phase"] in (
                        "armed",
                        "injected",
                        "observing",
                        "recovering",
                        "verifying",
                    ):
                        store.mark_uncertain(
                            conn,
                            trial_id,
                            fence_token=token,
                            reason="Executor interrupted or verification unavailable",
                        )
                    elif not row.get("dispatch_intent_at") and row["phase"] in (
                        "requested",
                        "preflight",
                        "armed",
                    ):
                        store.request_abort(conn, trial_id)
                        result["status"] = "ABORTED"
            except Exception:
                result["ledger_reconciliation_required"] = True
    finally:
        try:
            resources_stack.close()
        except Exception:
            result["access_cleanup_failed"] = True
            if result["status"] == "SUCCEEDED":
                result["status"] = "INDETERMINATE"
    result["ended_at"] = utc()
    result["execution_error"] = injection_error
    result["cleanup_error"] = cleanup_error
    if "capacity_record" in adapter.state:
        capacity = adapter.state["capacity_record"]
        capacity["passed"] = result["status"] == "SUCCEEDED"
        capacity["failure"] = None if capacity["passed"] else result["status"]
        capacity["run_id"] = run_id
        write_json(directory / "capacity.json", capacity)
    write_json(directory / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", choices=sorted(ADAPTERS), required=True)
    parser.add_argument("--acknowledge", required=True)
    parser.add_argument("--capacity-mode", choices=("fixed", "hpa", "keda"))
    args = parser.parse_args()
    result = execute(args.scenario, args.acknowledge, args.capacity_mode)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "SUCCEEDED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
