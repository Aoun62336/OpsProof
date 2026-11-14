"""Safety-gated k6 orchestration with an OWNED local k3d port-forward.

Creates bounded ordinary demo jobs, not chaos or recovery actions. Unlike a
manual port-forward, this runner refuses to load-test an unrelated process
on port 18088 or a context pointing at AWS. Persists failing output too.
"""

import argparse
import json
import os
import re
import socket
import subprocess
import time
from pathlib import Path

from scripts.m5.preflight import memory_available

if __package__:
    from .contracts import (
        assert_bounded_workload,
        assert_isolated_k3d_api,
        assert_local_scope,
    )
    from .reconcile_jobs import parse_receipts, reconcile
else:
    from contracts import (
        assert_bounded_workload,
        assert_isolated_k3d_api,
        assert_local_scope,
    )
    from reconcile_jobs import parse_receipts, reconcile

PORT = 18088


def assert_port_free(port: int = PORT) -> None:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", port))


def local_prefix(kubeconfig: Path) -> list[str]:
    assert_local_scope(kubeconfig=kubeconfig, context="k3d-opsproof", mutation=False)
    prefix = [
        "kubectl",
        "--kubeconfig",
        str(kubeconfig.resolve()),
        "--context",
        "k3d-opsproof",
    ]
    config = subprocess.check_output(
        [*prefix, "config", "view", "--minify", "-o", "json"], text=True, timeout=10
    )
    assert_isolated_k3d_api(json.loads(config)["clusters"][0]["cluster"]["server"])
    return prefix


def wait_for_owned_forward(proc: subprocess.Popen, timeout: int = 20) -> None:
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if proc.poll() is not None:
            raise RuntimeError("Owned Kubernetes port-forward exited before ready")
        try:
            with socket.create_connection(("127.0.0.1", PORT), timeout=1):
                return
        except OSError:
            time.sleep(0.2)
    raise TimeoutError("Owned Kubernetes port-forward readiness timeout")


def execute(args):
    if args.acknowledge != "M6_LOCAL_DURABLE_JOBS":
        raise ValueError("Explicit local test-data write acknowledgment required")
    if not re.fullmatch(r"m6-[a-z0-9-]{8,36}", args.run_id):
        raise ValueError("Expected a fresh m6- prefixed lowercase run ID")
    if not 1 <= args.rate <= 5 or not 10 <= args.seconds <= 120:
        raise ValueError("Rate or seconds outside bounded limits")
    if not 1 <= args.vus <= 16 or not 1 <= args.timeout <= 600:
        raise ValueError("VU or verification deadline out of bounds")
    count = args.rate * args.seconds
    assert_bounded_workload(count=count, duration_ms=args.duration_ms)
    kube = local_prefix(args.kubeconfig)
    if memory_available() < 2 * 1024**3:
        raise RuntimeError("Host RAM below 2 GiB; refusing additional load")
    assert_port_free()
    # Keep generated artifacts in the existing ignored, local-only runtime tree.
    allowed_output = Path(".runtime/m6").resolve()
    if args.output_root.resolve() != allowed_output:
        raise ValueError("Only the ignored .runtime/m6 evidence directory is allowed")
    evidence = args.output_root / args.run_id
    if evidence.exists():
        raise ValueError("Run evidence directory already exists: refuse implicit overwrite/replay")
    evidence.mkdir(parents=True)
    logs = evidence / "k6-receipts.log"
    summary = evidence / "k6-summary.json"
    result_file = evidence / "exact-job-results.json"
    env = {
        **os.environ,
        "M6_RUN_ID": args.run_id,
        "M6_BASE_URL": "http://127.0.0.1:18088",
        "M6_RATE": str(args.rate),
        "M6_SECONDS": str(args.seconds),
        "M6_DURATION_MS": str(args.duration_ms),
        "M6_VUS": str(args.vus),
        "M6_SUMMARY_PATH": summary.resolve().relative_to(Path.cwd()).as_posix(),
    }
    proc = subprocess.Popen(
        [
            *kube,
            "port-forward",
            "-n",
            "opsproof-demo",
            "svc/demo-api",
            f"{PORT}:8080",
            "--address",
            "127.0.0.1",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_owned_forward(proc)
        with logs.open("w", encoding="utf-8") as output:
            load = subprocess.Popen(
                ["k6", "run", "--log-format", "raw", "benchmarks/k6/jobs.js"],
                stdout=output,
                stderr=subprocess.STDOUT,
                env=env,
            )
            deadline = time.monotonic() + args.seconds + 60
            try:
                while load.poll() is None:
                    if memory_available() < 1024**3:
                        raise RuntimeError("Host RAM below 1 GiB: bounded load aborted")
                    if proc.poll() is not None:
                        raise RuntimeError("Local port-forward unexpectedly exited")
                    if time.monotonic() > deadline:
                        raise TimeoutError("k6 exceeded bounded runtime")
                    time.sleep(1)
            except BaseException:
                load.terminate()
                try:
                    load.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    load.kill()
                    load.wait(timeout=5)
                raise
            if load.returncode != 0:
                raise RuntimeError("k6 thresholds/runtime failed; receipts preserved for audit")
        ids = parse_receipts(logs, args.run_id, count)
        report = reconcile("http://127.0.0.1:18088", ids, timeout=args.timeout)
        result_file.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        return {"passed": True, "count": len(ids), "evidence": str(evidence)}
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kubeconfig", type=Path, default=Path(".runtime/m5/kubeconfig.yaml"))
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--rate", type=int, default=2)
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--duration-ms", type=int, default=250)
    parser.add_argument("--vus", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--output-root", type=Path, default=Path(".runtime/m6"))
    parser.add_argument("--acknowledge", required=True)
    args = parser.parse_args()
    if not 1 <= args.vus <= 16 or not 1 <= args.timeout <= 600:
        parser.error("VU or verification deadline out of bounds")
    report = execute(args)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
