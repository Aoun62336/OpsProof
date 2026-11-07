"""Bounded in-cluster workload shared verbatim by fixed/HPA/KEDA trials.

No credentials, cloud calls, or mutations other than 60 ordinary demo jobs.
"""

import concurrent.futures
import json
import statistics
import threading
import time
from datetime import datetime
from urllib.request import Request, urlopen
from uuid import uuid4

BASE = "http://demo-api.opsproof-demo.svc.cluster.local:8080"
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
            except Exception:
                failure = True
            with lock:
                stats["requests"] += 1
                stats["failures"] += failure
                stats["latencies_ms"].append((time.monotonic() - then) * 1000)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(traffic, worker) for worker in range(8)]
        for _ in range(COUNT):
            item = request("/api/v1/jobs", {"duration_ms": DURATION_MS}, str(uuid4()))
            jobs.append(item["id"])
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
            datetime.fromisoformat(job["completed_at"])
            - datetime.fromisoformat(job["created_at"])
        ).total_seconds()
        for job in completed
    ]
    result = {
        "type": "result",
        "count": COUNT,
        "duration_ms": DURATION_MS,
        "load_seconds": LOAD_SECONDS,
        "target_requests_per_second": REQUESTS_PER_SECOND,
        "http_requests": stats["requests"],
        "http_failures": stats["failures"],
        "http_p95_ms": sorted(stats["latencies_ms"])[
            int(len(stats["latencies_ms"]) * 0.95)
        ],
        "job_p50_seconds": statistics.median(job_latency),
        "job_p95_seconds": sorted(job_latency)[int(COUNT * 0.95)],
        "job_elapsed_seconds": elapsed,
        "jobs_per_second": COUNT / elapsed,
        "jobs": completed,
    }
    print(json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
