"""Verify real HTTP 401 responses, never treating an unreachable service as success."""

import json
from urllib.error import HTTPError
from urllib.request import Request, urlopen

CHECKS = [
    ("control capabilities", "GET", "http://127.0.0.1:8090/api/v1/capabilities", None),
    (
        "investigation creation",
        "POST",
        "http://127.0.0.1:8090/api/v1/investigations",
        {"incident_fingerprint": "a" * 16},
    ),
    (
        "recovery proposal",
        "POST",
        "http://127.0.0.1:8090/api/v1/recoveries",
        {"investigation_id": "00000000-0000-0000-0000-000000000001"},
    ),
    (
        "demo inspection",
        "GET",
        "http://127.0.0.1:8088/api/v1/internal/worker-state",
        None,
    ),
    (
        "demo actuator",
        "POST",
        "http://127.0.0.1:8088/api/v1/internal/worker/resume",
        {"recovery_id": "00000000-0000-0000-0000-000000000001"},
    ),
]


def main() -> None:
    for name, method, url, body in CHECKS:
        request = Request(
            url,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Content-Type": "application/json",
                "Idempotency-Key": "unauthenticated-m4-check",
            },
        )
        try:
            with urlopen(request, timeout=5) as response:
                code = response.status
        except HTTPError as exc:
            code = exc.code
        if code != 401:
            raise RuntimeError(f"{name}: expected HTTP 401, received {code}")
        print(f"PASS: {name}: HTTP 401")
    print("PASS: all unauthenticated routes rejected")


if __name__ == "__main__":
    main()
