"""HTTP smoke checks and worker-outage verification."""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from time import sleep, monotonic
from uuid import uuid4
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

BASE_URL = "http://127.0.0.1:8088"
RUN_FILE = Path(".runtime/outage_run.json")
TIMEOUT_S = 60


def request(
    method: str,
    path: str,
    body: dict | None = None,
    idempotency_key: str | None = None,
) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except HTTPError as exc:
        body_bytes = exc.read()
        try:
            payload = json.loads(body_bytes)
        except Exception:
            payload = {"raw": body_bytes.decode(errors="replace")}
        return exc.code, payload


def submit(count: int) -> list[str]:
    ids = []
    for _ in range(count):
        key = str(uuid4())
        code, job = request(
            "POST",
            "/api/v1/jobs",
            {"duration_ms": 500},
            key,
        )
        assert code == 202, f"Expected 202, got {code}: {job}"
        ids.append(job["id"])
    return ids


def wait_completed(ids: list[str]) -> None:
    deadline = monotonic() + TIMEOUT_S
    remaining = set(ids)
    while remaining:
        if monotonic() > deadline:
            raise TimeoutError(
                f"{len(remaining)} jobs did not complete before deadline"
            )
        for job_id in list(remaining):
            code, job = request(
                "GET",
                f"/api/v1/jobs/{job_id}",
            )
            if code != 200:
                raise RuntimeError(
                    f"Cannot inspect job {job_id}: HTTP {code}"
                )
            status = job["status"]
            if status == "failed":
                raise RuntimeError(
                    f"Job {job_id} failed; recovery is not successful"
                )
            if status == "completed":
                remaining.discard(job_id)
        if remaining:
            sleep(1)


def smoke() -> None:
    assert request("GET", "/health/ready")[0] == 200

    key = str(uuid4())
    code, job = request(
        "POST",
        "/api/v1/jobs",
        {"duration_ms": 200},
        key,
    )
    assert code == 202

    again_code, again = request(
        "POST",
        "/api/v1/jobs",
        {"duration_ms": 200},
        key,
    )
    assert again_code == 202
    assert again["id"] == job["id"]

    conflict_code, _ = request(
        "POST",
        "/api/v1/jobs",
        {"duration_ms": 500},
        key,
    )
    assert conflict_code == 409

    wait_completed([job["id"]])

    print(
        "PASS: readiness, idempotency, "
        "conflict rejection, completed job"
    )


def outage_submit() -> None:
    ids = submit(6)
    states = [
        request(
            "GET",
            f"/api/v1/jobs/{job_id}",
        )[1]["status"]
        for job_id in ids
    ]
    assert all(
        state == "queued" for state in states
    ), states

    RUN_FILE.parent.mkdir(exist_ok=True)
    report = {
        "scenario": "worker-stopped",
        "ids": ids,
        "created_at": datetime.now(UTC).isoformat(),
    }
    RUN_FILE.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    print(f"Recorded {len(ids)} queued job IDs to {RUN_FILE}")


def outage_verify() -> None:
    if not RUN_FILE.exists():
        print(f"ERROR: {RUN_FILE} not found. Run outage-submit first.")
        sys.exit(1)

    report = json.loads(RUN_FILE.read_text(encoding="utf-8"))
    ids = report["ids"]
    print(f"Verifying {len(ids)} jobs complete after worker restart...")
    wait_completed(ids)
    report["verified_at"] = datetime.now(UTC).isoformat()
    report["all_completed"] = True
    report["verified_job_count"] = len(ids)
    RUN_FILE.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )
    print(
        f"PASS: all {len(ids)} queued jobs "
        "completed after worker recovery"
    )


COMMANDS = {
    "smoke": smoke,
    "outage-submit": outage_submit,
    "outage-verify": outage_verify,
}

if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in COMMANDS:
        print(f"Usage: verify_demo.py [{' | '.join(COMMANDS)}]")
        sys.exit(1)
    COMMANDS[sys.argv[1]]()

