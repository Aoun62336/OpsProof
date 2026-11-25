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

# Session ownership survives the durable claim commit. A second evidence process
# cannot reap or dispatch AI work while the first still owns its connection.
AI_WORKER_LOCK = 74021443
AI_ABANDONED_SECONDS = 180  # Above either provider's HTTP timeout; never a retry lease.


def scrapes_fresh(vectors: list[list[dict]], now: float) -> bool:
    """Require matching, unique targets and recent healthy samples for every replica."""
    indexed = []
    for vector in vectors:
        targets = {}
        if not vector:
            raise ValueError("No scrape targets")
        for sample in vector:
            labels = sample["metric"]
            if not isinstance(labels, dict):
                raise ValueError("Invalid target labels")
            identity = tuple(
                sorted((key, value) for key, value in labels.items() if key != "__name__")
            )
            if not identity or identity in targets:
                raise ValueError("Ambiguous scrape targets")
            value = float(sample["value"][1])
            if not isfinite(value):
                raise ValueError("Nonfinite scrape evidence")
            targets[identity] = value
        indexed.append(targets)
    if len(indexed) != 2 or indexed[0].keys() != indexed[1].keys():
        raise ValueError("Scrape target sets changed during collection")
    return all(indexed[0][key] == 1 and 0 <= now - stamp <= 30 for key, stamp in indexed[1].items())


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
            vectors = []
            for query in ('up{job="opsproof-demo-api"}', 'timestamp(up{job="opsproof-demo-api"})'):
                checkpoint()
                response = client.get("/api/v1/query", params={"query": query})
                response.raise_for_status()
                data = response.json()
                if data["status"] != "success" or data["data"]["resultType"] != "vector":
                    raise ValueError("Invalid scrape response")
                vectors.append(data["data"]["result"])
            facts["scrape_fresh"] = scrapes_fresh(vectors, time())
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
        owned = conn.execute(
            "SELECT pg_try_advisory_lock(%s) AS owned", (AI_WORKER_LOCK,)
        ).fetchone()["owned"]
        if not owned:
            return
        try:
            conn.commit()
            conn.execute(
                "UPDATE investigations SET ai_status='failed', "
                "error='AI response unknown after worker interruption' "
                "WHERE ai_status='running' AND ai_started_at < "
                "now() - make_interval(secs => %s)",
                (AI_ABANDONED_SECONDS,),
            )
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
            # Persist before the external request. A crash must leave unknown
            # running work, never a queued request that another worker repeats.
            conn.commit()
            try:
                result = compare(Snapshot.model_validate(row["snapshot"]))
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
                conn.rollback()
                # Do not persist provider bodies, URLs, credentials or raw output.
                conn.execute(
                    "UPDATE investigations SET ai_status='failed', error=%s "
                    "WHERE id=%s AND ai_status='running'",
                    (f"AI evaluation failed: {type(exc).__name__}", row["id"]),
                )
            conn.commit()
        finally:
            # A pooled connection must never retain a session-level lock. If
            # cleanup fails, discard it; closing the session also drops ownership.
            try:
                conn.commit()
                conn.execute("SELECT pg_advisory_unlock(%s)", (AI_WORKER_LOCK,))
                conn.commit()
            except Exception:
                conn.close()
                raise
