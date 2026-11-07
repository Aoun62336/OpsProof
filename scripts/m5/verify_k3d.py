"""Bounded M5 cluster smoke, using only dedicated local port-forward ports.

Does not exercise recovery, external AI, release rollback or cloud resources.
"""

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from render_local_secrets import read_env


def http(
    base: str, method: str, path: str, key: str = "", idem: str = "", payload=None
):
    headers = {"Content-Type": "application/json"}
    if key:
        headers["X-OpsProof-Key"] = key
    if idem:
        headers["Idempotency-Key"] = idem
    data = json.dumps(payload).encode() if payload is not None else None
    request = Request(base + path, method=method, data=data, headers=headers)
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode())
        except ValueError:
            return exc.code, {}


def verify(env_path: Path):
    out = Path(".runtime/m5/k3d-smoke.json")
    out.unlink(missing_ok=True)
    env = read_env(env_path)
    key = env.get("OPSPROOF_CONTROL_API_KEY", "")
    if not key:
        raise RuntimeError("Control operator key not found in local .env")
    demo = "http://127.0.0.1:18088"
    control = "http://127.0.0.1:18090"
    for base in (demo, control):
        code, response = http(base, "GET", "/health/ready")
        if code != 200 or response.get("status") != "ready":
            raise RuntimeError(
                f"Readiness failed at local port {base.rsplit(':', 1)[1]}"
            )
    payload = {"scenario": "queue-burst", "count": 5, "duration_ms": 250}
    idem = str(uuid4())
    unauthorized, _ = http(
        control, "POST", "/api/v1/experiments", idem=idem, payload=payload
    )
    if unauthorized != 401:
        raise RuntimeError("Anonymous experiment creation was not denied")
    created_code, created = http(
        control, "POST", "/api/v1/experiments", key, idem, payload
    )
    if created_code != 202 or not created.get("id"):
        raise RuntimeError("Authenticated bounded experiment not accepted")
    run_id = created["id"]
    dup_code, duplicate = http(
        control, "POST", "/api/v1/experiments", key, idem, payload
    )
    if dup_code != 202 or duplicate.get("id") != run_id:
        raise RuntimeError("Idempotency contract failed")
    status = "unknown"
    result = {}
    deadline = time.monotonic() + 140
    while time.monotonic() < deadline:
        code, item = http(control, "GET", f"/api/v1/experiments/{run_id}", key)
        if code != 200:
            raise RuntimeError("Experiment read failed")
        status = item.get("status", "unknown")
        result = item.get("result") or {}
        if status in ("succeeded", "failed"):
            break
        time.sleep(2)
    if status != "succeeded" or result.get("verified_completed") != 5:
        raise RuntimeError(f"Expected five verified jobs; observed status={status}")
    event_code, events = http(
        control, "GET", f"/api/v1/experiments/{run_id}/events", key
    )
    types = (
        {event.get("type") for event in events}
        if event_code == 200 and isinstance(events, list)
        else set()
    )
    if not {"jobs_processed", "verified"}.issubset(types):
        raise RuntimeError("Durable exact-job event evidence missing")
    job_ids = result.get("job_ids", [])
    if len(job_ids) != 5 or len(set(job_ids)) != 5:
        raise RuntimeError("Expected five distinct durable job IDs")
    jobs = []
    for job_id in job_ids:
        code, job = http(demo, "GET", f"/api/v1/jobs/{job_id}")
        if code != 200 or job.get("id") != job_id or job.get("status") != "completed":
            raise RuntimeError("Independent exact-job read failed")
        jobs.append({"id": job_id, "status": job["status"]})
    record = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "run_id": run_id,
        "status": status,
        "verified_completed": 5,
        "jobs": jobs,
        "event_types": sorted(types),
        "environment": "local k3d port-forward 18088/18090",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"K3d smoke verified 5 jobs. Run ID: {run_id}; evidence: {out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default=".env")
    args = parser.parse_args()
    try:
        verify(Path(args.env))
    except (OSError, URLError, RuntimeError, ValueError, TimeoutError) as exc:
        raise SystemExit(f"K3d smoke FAILED: {type(exc).__name__}: {exc}") from exc
