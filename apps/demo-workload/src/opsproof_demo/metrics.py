"""Bounded HTTP and durable-state metrics, independently scraped by Prometheus."""

from threading import Lock
from time import perf_counter, time

from fastapi import FastAPI, Request
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest
from redis import Redis

from .config import settings
from .db import pool

REQUESTS = Counter("opsproof_http_requests", "HTTP requests", ["method", "route", "status"])
DURATION = Histogram(
    "opsproof_http_request_duration_seconds",
    "HTTP request durations",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)
STATES = ("queued", "processing", "completed", "failed")
COUNTS = Gauge("opsproof_demo_jobs", "Durable jobs by state", ["state"])
READY = Gauge("opsproof_demo_dependencies_ready", "PostgreSQL and Redis readiness")
DEPENDENCIES = Gauge("opsproof_demo_dependency_ready", "Dependency probe success", ["dependency"])
STATE_UPDATED = Gauge(
    "opsproof_demo_state_last_success_timestamp_seconds",
    "Last successful durable-state observation, Unix seconds",
)
AGES = Gauge(
    "opsproof_demo_oldest_active_age_seconds", "Age of oldest unfinished item, seconds", ["state"]
)
LAST_COMPLETION = Gauge(
    "opsproof_demo_last_completion_timestamp_seconds",
    "Latest durable successful completion, Unix seconds",
)
ACTIVE_STATES = ("queued", "processing")
SCRAPE_LOCK = Lock()
METHODS = frozenset(
    ("GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT")
)


def refresh_state() -> None:
    database_ready = False
    redis_ready = False
    try:
        with pool().connection(timeout=2) as conn:
            conn.execute("SET LOCAL statement_timeout = '2s'")
            rows = conn.execute("""SELECT status, COUNT(*) AS n,
                       GREATEST(0, EXTRACT(EPOCH FROM (now() - MIN(
                           CASE WHEN status = 'queued' THEN created_at
                                ELSE COALESCE(started_at, created_at) END)))) AS age_seconds,
                       MAX(EXTRACT(EPOCH FROM completed_at)) AS last_completion
                FROM jobs GROUP BY status""").fetchall()
        counts = {row["status"]: row["n"] for row in rows}
        for state in STATES:
            COUNTS.labels(state=state).set(counts.get(state, 0))
        by_state = {row["status"]: row for row in rows}
        for state in ACTIVE_STATES:
            AGES.labels(state=state).set(float(by_state.get(state, {}).get("age_seconds") or 0))
        LAST_COMPLETION.set(float(by_state.get("completed", {}).get("last_completion") or 0))
        STATE_UPDATED.set(time())
        database_ready = True
    except Exception:
        for state in STATES:
            COUNTS.labels(state=state).set(float("nan"))
        for state in ACTIVE_STATES:
            AGES.labels(state=state).set(float("nan"))
        LAST_COMPLETION.set(float("nan"))
    try:
        with Redis.from_url(
            settings().redis_url, socket_connect_timeout=2, socket_timeout=2
        ) as client:
            client.ping()
        redis_ready = True
    except Exception:
        pass
    DEPENDENCIES.labels(dependency="postgresql").set(int(database_ready))
    DEPENDENCIES.labels(dependency="redis").set(int(redis_ready))
    READY.set(int(database_ready and redis_ready))


def install_metrics(app: FastAPI) -> None:
    @app.middleware("http")
    async def measure(request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)
        started = perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            # Matched templates, never raw URLs or identifiers. Unknown methods are bounded too.
            route = getattr(request.scope.get("route"), "path", "unmatched")
            method = request.method if request.method in METHODS else "OTHER"
            REQUESTS.labels(method=method, route=route, status=str(status)).inc()
            DURATION.labels(method=method, route=route).observe(perf_counter() - started)

    @app.get("/metrics", include_in_schema=False)
    def metrics() -> Response:
        with SCRAPE_LOCK:
            refresh_state()
            return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})
