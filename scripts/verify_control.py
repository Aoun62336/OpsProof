"""End-to-end verification of the OpsProof control plane."""

import json
import time
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


BASE_URL = "http://127.0.0.1:8090"
OUTPUT = Path(".runtime/control-first-run.json")


def api_key() -> str:
    env_file = Path(".env")

    for line in env_file.read_text(
        encoding="utf-8"
    ).splitlines():
        if line.startswith("OPSPROOF_CONTROL_API_KEY="):
            return line.split("=", 1)[1].strip()

    raise RuntimeError(
        "OPSPROOF_CONTROL_API_KEY not found in .env"
    )


def request(
    method: str,
    path: str,
    payload: dict | None = None,
    key: str | None = None,
    authenticated: bool = True,
) -> tuple[int, dict | list]:
    headers = {
        "Content-Type": "application/json",
    }

    if authenticated:
        headers["X-OpsProof-Key"] = api_key()

    if key is not None:
        headers["Idempotency-Key"] = key

    body = (
        json.dumps(payload).encode("utf-8")
        if payload is not None
        else None
    )

    req = Request(
        f"{BASE_URL}{path}",
        data=body,
        headers=headers,
        method=method,
    )

    try:
        with urlopen(req, timeout=5) as response:
            data = json.load(response)
            return response.status, data

    except HTTPError as exc:
        data = json.loads(
            exc.read().decode("utf-8")
        )
        return exc.code, data


def verify() -> None:
    ready_code, ready = request(
        "GET",
        "/health/ready",
        authenticated=False,
    )

    assert ready_code == 200, ready

    run_key = str(uuid4())

    payload = {
        "scenario": "queue-burst",
        "count": 5,
        "duration_ms": 250,
    }

    unauthorized_code, _ = request(
        "POST",
        "/api/v1/experiments",
        payload,
        key=run_key,
        authenticated=False,
    )

    assert unauthorized_code == 401

    created_code, created = request(
        "POST",
        "/api/v1/experiments",
        payload,
        key=run_key,
    )

    assert created_code == 202, created

    run_id = created["id"]

    duplicate_code, duplicate = request(
        "POST",
        "/api/v1/experiments",
        payload,
        key=run_key,
    )

    assert duplicate_code == 202
    assert duplicate["id"] == run_id

    conflict_payload = {
        **payload,
        "count": 6,
    }

    conflict_code, _ = request(
        "POST",
        "/api/v1/experiments",
        conflict_payload,
        key=run_key,
    )

    assert conflict_code == 409

    print(f"Created experiment: {run_id}")
    print("Waiting for controlled job processing...")

    deadline = time.monotonic() + 120

    while time.monotonic() < deadline:
        code, result = request(
            "GET",
            f"/api/v1/experiments/{run_id}",
        )

        assert code == 200

        if result["status"] == "succeeded":
            break

        if result["status"] == "failed":
            raise RuntimeError(
                f"Experiment failed: {result['error']}"
            )

        time.sleep(1)

    else:
        raise TimeoutError(
            "Control-plane experiment did not finish"
        )

    assert result["result"]["submitted"] == 5
    assert result["result"]["verified_completed"] == 5

    events_code, events = request(
        "GET",
        f"/api/v1/experiments/{run_id}/events",
    )

    assert events_code == 200

    event_types = {
        item["type"]
        for item in events
    }

    required_events = {
        "created",
        "started",
        "jobs_processed",
        "verified",
    }

    assert required_events.issubset(event_types)

    report = {
        "experiment": result,
        "events": events,
        "verification": {
            "authenticated_access": True,
            "idempotent_submission": True,
            "conflicting_submission_rejected": True,
            "completed_jobs": 5,
            "required_events_present": True,
        },
    }

    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    OUTPUT.write_text(
        json.dumps(report, indent=2),
        encoding="utf-8",
    )

    print("PASS: authenticated control API")
    print("PASS: duplicate request protection")
    print("PASS: conflicting request rejected")
    print("PASS: action worker completed sandbox jobs")
    print("PASS: evidence worker verified completion")
    print("PASS: experiment history preserved")
    print(f"Evidence: {OUTPUT}")


if __name__ == "__main__":
    verify()