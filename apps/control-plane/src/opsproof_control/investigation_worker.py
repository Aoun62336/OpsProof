"""Bounded read-only evidence collection and durable investigation polling."""

import logging
from datetime import UTC, datetime
from math import isfinite
from time import time
from uuid import UUID

import httpx2 as httpx
from psycopg.types.json import Jsonb

from .config import settings
from .db import pool
from .diagnosis import Snapshot, deterministic
from .shutdown import checkpoint

logger = logging.getLogger(__name__)


def collect(incident: dict, run_id: UUID | None) -> Snapshot:
    config = settings()
    observed_at = datetime.now(UTC)
    errors: list[str] = []
    jobs: list[UUID] = []
    if run_id is not None:
        with pool().connection() as conn:
            run = conn.execute("SELECT * FROM experiments WHERE id = %s", (run_id,)).fetchone()
            event = conn.execute(
                "SELECT details FROM experiment_events WHERE run_id = %s "
                "AND type IN ('jobs_processed','action_completed') ORDER BY id DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        try:
            jobs = [UUID(value) for value in event["details"]["job_ids"]]
            if (
                not run
                or run["scenario"] != "queue-burst"
                or run["status"] != "verifying"
                or len(jobs) != run["count"]
                or not 1 <= len(jobs) <= 8
                or len(set(jobs)) != len(jobs)
            ):
                raise ValueError("Invalid linked experiment")
        except KeyError, TypeError, ValueError:
            jobs = []
            errors.append("Linked experiment evidence unavailable or ineligible")
    facts = {}
    with httpx.Client(base_url=config.target_url, timeout=3, trust_env=False) as client:
        try:
            checkpoint()
            response = client.get("/health/ready")
            facts["api_ready"] = response.status_code == 200
        except httpx.HTTPError:
            facts["api_ready"] = False
            errors.append("Demo readiness unavailable")
        try:
            checkpoint()
            response = client.get("/api/v1/stats")
            response.raise_for_status()
            stats = response.json()
            for key in ("queued", "processing"):
                value = stats[key]
                if type(value) is not int or not 0 <= value <= 1_000_000:
                    raise ValueError("Invalid job counts")
                facts[key] = value
        except httpx.HTTPError, ValueError, KeyError, TypeError:
            errors.append("Demo job counts unavailable")
        try:
            checkpoint()
            response = client.get(
                "/api/v1/internal/worker-state",
                headers={
                    "X-OpsProof-Inspect-Key": config.inspection_key,
                },
            )
            response.raise_for_status()
            state = response.json()
            if (
                type(state["paused"]) is not bool
                or type(state["ttl_seconds"]) is not int
                or not 0 <= state["ttl_seconds"] <= 480
            ):
                raise ValueError("Invalid hold state")
            facts.update(worker_paused=state["paused"], hold_ttl_seconds=state["ttl_seconds"])
        except httpx.HTTPError, ValueError, KeyError, TypeError:
            errors.append("Demo hold state unavailable")
    try:
        with httpx.Client(base_url=config.prometheus_url, timeout=3, trust_env=False) as client:
            # timestamp(up) returns the underlying sample time, not the query evaluation time.
            values = []
            for query in ('up{job="opsproof-demo-api"}', 'timestamp(up{job="opsproof-demo-api"})'):
                checkpoint()
                response = client.get("/api/v1/query", params={"query": query})
                response.raise_for_status()
                data = response.json()
                result = data["data"]["result"]
                if data["status"] != "success" or len(result) != 1:
                    raise ValueError("Ambiguous scrape evidence")
                values.append(float(result[0]["value"][1]))
            facts["scrape_fresh"] = (
                all(isfinite(v) for v in values)
                and values[0] == 1
                and 0 <= time() - values[1] <= 30
            )
    except httpx.HTTPError, ValueError, KeyError, TypeError:
        errors.append("Prometheus scrape evidence unavailable")
    return Snapshot(
        observed_at=observed_at,
        incident_fingerprint=incident["fingerprint"],
        alert_name=incident["name"],
        target=incident["target"],
        incident_status=incident["status"],
        run_id=run_id,
        job_ids=jobs,
        errors=errors,
        **facts,
    )


def process_next_investigation() -> None:
    with pool().connection() as conn:
        # Interrupted read-only work can be retried; interrupted paid work cannot.
        conn.execute(
            "UPDATE investigations SET status='queued' WHERE status='running' "
            "AND started_at < now() - interval '60 seconds'"
        )
        conn.execute(
            "UPDATE investigations SET ai_status='failed', "
            "error='AI response unknown after worker interruption' "
            "WHERE ai_status='running' AND ai_started_at < now() - interval '60 seconds'"
        )
        row = conn.execute(
            "SELECT * FROM investigations WHERE status='queued' "
            "ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"
        ).fetchone()
        if row:
            conn.execute(
                "UPDATE investigations SET status='running', started_at=now() WHERE id=%s",
                (row["id"],),
            )
    if row:
        try:
            with pool().connection() as conn:
                incident = conn.execute(
                    "SELECT * FROM incidents WHERE fingerprint=%s", (row["incident_fingerprint"],)
                ).fetchone()
            snapshot = collect(incident, row["run_id"])
            baseline = deterministic(snapshot)
            with pool().connection() as conn:
                conn.execute(
                    "UPDATE investigations SET status='ready', snapshot=%s, baseline=%s, "
                    "completed_at=now(), error=NULL WHERE id=%s AND status='running'",
                    (
                        Jsonb(snapshot.model_dump(mode="json")),
                        Jsonb(baseline.model_dump()),
                        row["id"],
                    ),
                )
        except Exception as exc:
            logger.warning("Investigation failed: %s", type(exc).__name__)
            with pool().connection() as conn:
                conn.execute(
                    "UPDATE investigations SET status='failed', error=%s, "
                    "completed_at=now() WHERE id=%s AND status='running'",
                    (f"Evidence collection failed: {type(exc).__name__}", row["id"]),
                )
    checkpoint()
    process_next_ai()


def process_next_ai() -> None:
    from .model_provider import compare

    with pool().connection() as conn:
        row = conn.execute(
            "SELECT * FROM investigations WHERE ai_status='queued' "
            "ORDER BY ai_requested_at FOR UPDATE SKIP LOCKED LIMIT 1"
        ).fetchone()
        if not row:
            return
        conn.execute(
            "UPDATE investigations SET ai_status='running', ai_started_at=now() WHERE id=%s",
            (row["id"],),
        )
    try:
        result = compare(Snapshot.model_validate(row["snapshot"]))
        with pool().connection() as conn:
            conn.execute(
                "UPDATE investigations SET ai_status='ready', ai_result=%s, "
                "ai_provider=%s, ai_model=%s, ai_usage=%s, ai_elapsed_ms=%s "
                "WHERE id=%s AND ai_status='running'",
                (
                    Jsonb(result["diagnosis"]),
                    result["provider"],
                    result["model"],
                    Jsonb(result["usage"]),
                    result["elapsed_ms"],
                    row["id"],
                ),
            )
    except Exception as exc:
        # Never persist provider exception bodies, URLs, keys or raw model responses.
        with pool().connection() as conn:
            conn.execute(
                "UPDATE investigations SET ai_status='failed', error=%s "
                "WHERE id=%s AND ai_status='running'",
                (f"AI evaluation failed: {type(exc).__name__}", row["id"]),
            )
