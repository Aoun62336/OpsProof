"""M6 capacity v2: bounded Python load, immediate receipts, nearest-rank p95.

Based on the preserved M5 protocol; separate from k6 and historical M5 results.
"""

import concurrent.futures
import json
import math
import os
import statistics
import threading
import time
from datetime import datetime
from urllib.error import URLError
from urllib.request import Request, urlopen

BASE = "http://demo-api.opsproof-demo.svc.cluster.local:8080"
if os.environ.get("M6_LOAD_TARGET") == "owned-local-forward":
    BASE = "http://127.0.0.1:18088"
COUNT = 60
DURATION_MS = 2000
LOAD_SECONDS = 120
REQUESTS_PER_SECOND = 80


def request(path, payload=None, idem=None):
    headers = {"Content-Type": "application/json"}
    if idem:
        headers["Idempotency-Key"] = idem
    req = Request(
        BASE + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers=headers,
    )
    with urlopen(req, timeout=5) as response:
        return json.load(response)


def main():
    # New Pod policy/service rules can take time to converge. Keep this bounded
    # readiness warmup separate from measured traffic and report its failures.
    warmup_started = time.monotonic()
    warmup_failures = 0
    consecutive = 0
    while consecutive < 5:
        try:
            request("/health/ready")
            consecutive += 1
        except URLError, TimeoutError:
            warmup_failures += 1
            consecutive = 0
        if time.monotonic() - warmup_started > 30:
            raise RuntimeError("Service did not become ready during bounded warmup")
        time.sleep(1)
    started = time.monotonic()
    stats = {"requests": 0, "failures": 0, "latencies_ms": []}
    lock = threading.Lock()
    jobs = []

    def traffic(worker):
        deadline = started + LOAD_SECONDS
        tick = time.monotonic() + worker / REQUESTS_PER_SECOND
        while time.monotonic() < deadline:
            time.sleep(max(0, tick - time.monotonic()))
            tick += 8 / REQUESTS_PER_SECOND
            then = time.monotonic()
            failure = False
            try:
                request("/health/ready")
            except Exception:  # noqa: BLE001 - every failed request is counted and fails acceptance
                failure = True
            with lock:
                stats["requests"] += 1
                stats["failures"] += failure
                stats["latencies_ms"].append((time.monotonic() - then) * 1000)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(traffic, worker) for worker in range(8)]
        for index in range(COUNT):
            key = os.environ["M6_RUN_ID"] + "-" + str(index)
            print(json.dumps({"type": "intent", "key": key}), flush=True)
            item = request("/api/v1/jobs", {"duration_ms": DURATION_MS}, key)
            jobs.append(item["id"])
            print(
                json.dumps({"type": "receipt", "id": item["id"], "key": key}),
                flush=True,
            )
            time.sleep(0.1)
        print(json.dumps({"type": "submitted", "job_ids": jobs}), flush=True)
        remaining = set(jobs)
        completed = []
        deadline = started + 300
        while remaining and time.monotonic() < deadline:
            for job_id in list(remaining):
                item = request("/api/v1/jobs/" + job_id)
                if item.get("id") != job_id:
                    raise RuntimeError("Job identity mismatch")
                if item["status"] == "failed":
                    raise RuntimeError("Durable job failed")
                if item["status"] == "completed":
                    completed.append(item)
                    remaining.remove(job_id)
            time.sleep(1)
        for future in futures:
            future.result()
    if remaining or len(completed) != COUNT or len(set(jobs)) != COUNT:
        raise RuntimeError("Exact-job completion deadline/count failed")
    elapsed = (
        max(datetime.fromisoformat(job["completed_at"]) for job in completed)
        - min(datetime.fromisoformat(job["created_at"]) for job in completed)
    ).total_seconds()
    job_latency = [
        (
            datetime.fromisoformat(job["completed_at"]) - datetime.fromisoformat(job["created_at"])
        ).total_seconds()
        for job in completed
    ]
    result = {
        "type": "result",
        "protocol": "m6-python-capacity-v3-local",
        "warmup_seconds": started - warmup_started,
        "warmup_failures": warmup_failures,
        "count": COUNT,
        "duration_ms": DURATION_MS,
        "load_seconds": LOAD_SECONDS,
        "target_requests_per_second": REQUESTS_PER_SECOND,
        "http_requests": stats["requests"],
        "http_failures": stats["failures"],
        "http_p95_ms": sorted(stats["latencies_ms"])[
            math.ceil(len(stats["latencies_ms"]) * 0.95) - 1
        ],
        "job_p50_seconds": statistics.median(job_latency),
        "job_p95_seconds": sorted(job_latency)[math.ceil(COUNT * 0.95) - 1],
        "job_elapsed_seconds": elapsed,
        "jobs_per_second": COUNT / elapsed,
        "jobs": completed,
    }
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
