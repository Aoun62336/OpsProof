"""Verify a real demo trace, a real worker log, and the OTLP pipeline.

Run from the repository root with the full local Compose stack running.
Uses only the standard library and the existing control-api container as a
network-local probe; no collector port is exposed to the host.
"""

import base64
import json
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]


def get(url, headers=None):
    with urlopen(Request(url, headers=headers or {}), timeout=5) as response:
        return json.load(response)


def eventually(check, description):
    deadline = time.monotonic() + 90
    while time.monotonic() < deadline:
        try:
            if check():
                print(f"PASS: {description}", flush=True)
                return
        except HTTPError, URLError, TimeoutError:
            pass
        time.sleep(2)
    raise RuntimeError(f"Timed out: {description}")


def main():
    values = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip().strip("\"'")
    password = values["OPSPROOF_GRAFANA_ADMIN_PASSWORD"]
    auth = base64.b64encode(f"opsproof:{password}".encode()).decode()
    headers = {"Authorization": f"Basic {auth}"}
    trace_id = uuid4().hex
    marker = f"opsproof-telemetry-verification-{uuid4()}"
    started = time.time_ns()

    # The sampled parent makes this probe deterministic despite the normal 25%
    # root sampling policy. This is a real instrumented, read-only API request.
    stats = get(
        "http://127.0.0.1:8088/api/v1/stats",
        {"traceparent": f"00-{trace_id}-{uuid4().hex[:16]}-01"},
    )
    assert "queued" in stats

    # Marked synthetic log: exercise the actual OTLP receiver/processors/exporter
    # without creating an application failure merely to produce a log message.
    payload = {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "service.name",
                            "value": {"stringValue": "opsproof-verification"},
                        }
                    ]
                },
                "scopeLogs": [
                    {
                        "scope": {"name": "opsproof.telemetry.verification"},
                        "logRecords": [
                            {
                                "timeUnixNano": str(started),
                                "severityNumber": 9,
                                "severityText": "INFO",
                                "body": {"stringValue": marker},
                            }
                        ],
                    }
                ],
            }
        ],
    }
    probe = (
        "import json,sys,urllib.request\n"
        f"payload={payload!r}\n"
        "req=urllib.request.Request('http://otel-collector:4318/v1/logs',"
        "data=json.dumps(payload).encode(),headers={'Content-Type':'application/json'})\n"
        "with urllib.request.urlopen(req,timeout=10) as r:\n"
        " result=json.load(r)\n"
        " assert not result.get('partialSuccess',{}).get('rejectedLogRecords',0),result\n"
        " print('PASS: collector accepted marked OTLP log')\n"
    )
    subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "compose.control.yaml",
            "-f",
            "compose.control.telemetry.yaml",
            "-f",
            "compose.control.recovery.yaml",
            "exec",
            "-T",
            "control-api",
            "python",
            "-",
        ],
        input=probe,
        text=True,
        check=True,
        cwd=ROOT,
        timeout=30,
    )

    def has_trace(url, request_headers=None):
        data = get(url, request_headers)
        # Tempo's JSON trace response uses OTLP resourceSpans (or batches).
        spans = [
            span
            for batch in data.get("batches", data.get("resourceSpans", []))
            for scope in batch.get("scopeSpans", [])
            for span in scope.get("spans", [])
        ]
        expected = {trace_id, base64.b64encode(bytes.fromhex(trace_id)).decode()}
        return any(span.get("traceId") in expected for span in spans)

    def log_url(base, service, needle):
        # Values are locally generated UUID markers, not arbitrary user input.
        query = '{service_name="' + service + '"} |= "' + needle + '"'
        return (
            base
            + "/loki/api/v1/query_range?"
            + urlencode(
                {
                    "query": query,
                    "start": str(started - 1_000_000_000),
                    "end": str(time.time_ns()),
                    "limit": 20,
                }
            )
        )

    def has_log(base, service, needle, request_headers=None):
        data = get(log_url(base, service, needle), request_headers)
        return data.get("status") == "success" and any(
            needle in value[1] for stream in data["data"]["result"] for value in stream["values"]
        )

    # Unlike the synthetic collector probe, this job must be processed by the
    # real demo Redis Streams worker and emit its normal application log.
    job_request = Request(
        "http://127.0.0.1:8088/api/v1/jobs",
        data=json.dumps({"duration_ms": 50}).encode(),
        headers={
            "Content-Type": "application/json",
            "Idempotency-Key": f"otel-worker-log-{uuid4()}",
        },
        method="POST",
    )
    with urlopen(job_request, timeout=5) as response:
        job = json.load(response)
    job_id = str(job["id"])
    eventually(
        lambda: get(f"http://127.0.0.1:8088/api/v1/jobs/{job_id}").get("status") == "completed",
        "one real bounded demo job completed",
    )

    eventually(
        lambda: has_trace(f"http://127.0.0.1:3200/api/traces/{trace_id}"),
        "instrumented demo trace retrieved from Tempo",
    )
    eventually(
        lambda: has_log("http://127.0.0.1:3100", "opsproof-verification", marker),
        "marked synthetic OTLP log retrieved from Loki",
    )
    proxy = "http://127.0.0.1:3000/api/datasources/proxy/uid/"
    eventually(
        lambda: has_trace(proxy + f"opsproof-tempo/api/traces/{trace_id}", headers),
        "same trace retrieved through authenticated Grafana datasource",
    )
    eventually(
        lambda: has_log(proxy + "opsproof-loki", "opsproof-verification", marker, headers),
        "same synthetic log retrieved through authenticated Grafana datasource",
    )
    eventually(
        lambda: has_log("http://127.0.0.1:3100", "opsproof-demo-worker", job_id),
        "real demo worker completion log retrieved from Loki",
    )
    eventually(
        lambda: has_log(proxy + "opsproof-loki", "opsproof-demo-worker", job_id, headers),
        "same real worker log retrieved through authenticated Grafana datasource",
    )
    output = ROOT / ".runtime" / "observability-verification.json"
    output.parent.mkdir(exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "verified_at": datetime.now(UTC).isoformat(),
                "trace_id": trace_id,
                "log_marker": marker,
                "trace_source": "instrumented demo GET /api/v1/stats",
                "log_source": "explicit synthetic OTLP verification record",
                "worker_log_source": "real opsproof-demo-worker completed job message",
                "worker_job_id": job_id,
                "worker_log_loki": "passed",
                "worker_log_grafana": "passed",
                "tempo": "passed",
                "loki": "passed",
                "grafana_datasources": "passed",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Evidence: {output}")


if __name__ == "__main__":
    main()
