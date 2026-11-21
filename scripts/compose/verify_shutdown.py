"""Validate ordinary SIGTERM stop/restart on the running local sandbox.

Run from the project root: python -m scripts.compose.verify_shutdown
Creates one eight-job experiment and briefly stops/restarts the five workers.
Does not delete data, change credentials, or enable recovery/AI.
"""

import json
import subprocess
import time
from pathlib import Path
from urllib.request import urlopen
from uuid import uuid4

from scripts.compose.verify_control import request

DEMO = [
    "docker",
    "compose",
    "-f",
    "compose.yaml",
    "-f",
    "compose.target-integration.yaml",
    "-f",
    "compose.demo.telemetry.yaml",
    "-f",
    "compose.demo.recovery.yaml",
]
CONTROL = [
    "docker",
    "compose",
    "-f",
    "compose.control.yaml",
    "-f",
    "compose.control.telemetry.yaml",
    "-f",
    "compose.control.recovery.yaml",
]
OUTPUT = Path(".runtime/shutdown-verification.json")


def command(args):
    return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()


def api(path):
    status, data = request("GET", path)
    assert status == 200, (status, data)
    return data


def demo(path):
    with urlopen("http://127.0.0.1:8088" + path, timeout=5) as response:
        return json.load(response)


def wait_for(check, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.2)
    raise TimeoutError("Expected shutdown/restart state did not arrive")


def stop(compose, services, report, label):
    ids = command(compose + ["ps", "-q", *services]).split()
    assert len(ids) == len(services), (services, ids)
    started = time.monotonic()
    # No signal override and no timeout override: exercise the shipped Compose defaults.
    command(compose + ["stop", *services])
    elapsed = round(time.monotonic() - started, 3)
    states = []
    for container in ids:
        item = json.loads(command(["docker", "inspect", container]))[0]
        state = item["State"]
        assert state["Status"] == "exited" and state["ExitCode"] == 0, state
        assert not state["OOMKilled"], state
        states.append({"name": item["Name"], "exit_code": state["ExitCode"]})
    report[label] = {"elapsed_seconds": elapsed, "containers": states}
    print(f"PASS: {label}: exit 0 in {elapsed}s", flush=True)


def verify():
    report = {}
    stats = demo("/api/v1/stats")
    assert stats["queued"] == stats["processing"] == 0, "Finish existing jobs first"
    summary = api("/api/v1/summary")
    assert all(summary["counts"][state] == 0 for state in ("queued", "running", "verifying"))
    assert not any(
        row["status"] in ("pending_approval", "approved", "running", "verifying")
        for row in api("/api/v1/recoveries")
    ), "Finish or reject existing recoveries first"
    assert (
        command(
            DEMO
            + [
                "exec",
                "-T",
                "redis",
                "redis-cli",
                "EXISTS",
                "opsproof:demo:worker:hold:v1",
            ]
        )
        == "0"
    ), "Clear existing hold first"
    try:
        status, run = request(
            "POST",
            "/api/v1/experiments",
            {"scenario": "queue-burst", "count": 8, "duration_ms": 750},
            key=str(uuid4()),
        )
        assert status == 202, (status, run)
        run_id = run["id"]
        report["experiment_id"] = run_id
        wait_for(lambda: api(f"/api/v1/experiments/{run_id}")["status"] == "verifying")
        events = api(f"/api/v1/experiments/{run_id}/events")
        job_ids = next(e["details"]["job_ids"] for e in events if e["type"] == "jobs_processed")
        report["job_ids"] = job_ids
        processing = wait_for(
            lambda: next(
                (
                    job
                    for job in (demo(f"/api/v1/jobs/{id}") for id in job_ids)
                    if job["status"] == "processing"
                ),
                None,
            )
        )
        report["active_job_before_stop"] = processing
        stop(DEMO, ["worker"], report, "active_demo_worker")
        finished = demo(f"/api/v1/jobs/{processing['id']}")
        assert finished["status"] == "completed", finished
        assert finished["attempts"] == processing["attempts"], finished
        assert any(demo(f"/api/v1/jobs/{id}")["status"] == "queued" for id in job_ids)
        report["active_job_after_stop"] = finished

        wait_for(
            lambda: (
                int(
                    command(
                        CONTROL
                        + [
                            "exec",
                            "-T",
                            "control-redis",
                            "redis-cli",
                            "--raw",
                            "XPENDING",
                            "opsproof:evidence:v1",
                            "evidence-workers",
                        ]
                    ).splitlines()[0]
                )
                > 0
            )
        )
        stop(CONTROL, ["evidence-worker"], report, "active_evidence_worker")
        assert api(f"/api/v1/experiments/{run_id}")["status"] == "verifying"
        pending = command(
            CONTROL
            + [
                "exec",
                "-T",
                "control-redis",
                "redis-cli",
                "--raw",
                "XPENDING",
                "opsproof:evidence:v1",
                "evidence-workers",
            ]
        )
        assert int(pending.splitlines()[0]) > 0, "Unfinished evidence was acknowledged"
        report["evidence_pending_after_stop"] = pending
        stop(
            CONTROL,
            ["control-dispatcher", "action-worker"],
            report,
            "idle_control_workers",
        )
        stop(DEMO, ["dispatcher"], report, "idle_demo_dispatcher")
    finally:
        # Restore workers even if an assertion fails; leave all durable work recoverable.
        command(DEMO + ["start", "dispatcher", "worker"])
        command(CONTROL + ["start", "control-dispatcher", "action-worker", "evidence-worker"])

    result = wait_for(
        lambda: (
            value
            if (value := api(f"/api/v1/experiments/{run_id}"))["status"] == "succeeded"
            else None
        )
    )
    assert result["result"]["verified_completed"] == 8
    assert set(result["result"]["job_ids"]) == set(job_ids)
    jobs = [demo(f"/api/v1/jobs/{id}") for id in job_ids]
    assert all(job["status"] == "completed" and job["attempts"] == 1 for job in jobs), jobs
    report["completed_jobs"] = jobs
    report["experiment"] = result
    # Recheck both consumer processes with no work, including the review-thread join.
    try:
        stop(DEMO, ["dispatcher", "worker"], report, "all_demo_workers_idle")
        stop(
            CONTROL,
            ["control-dispatcher", "action-worker", "evidence-worker"],
            report,
            "all_control_workers_idle",
        )
    finally:
        command(DEMO + ["start", "dispatcher", "worker"])
        command(CONTROL + ["start", "control-dispatcher", "action-worker", "evidence-worker"])
    OUTPUT.parent.mkdir(exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"PASS: exact jobs completed once; evidence resumed after restart. Evidence: {OUTPUT}")


if __name__ == "__main__":
    verify()
