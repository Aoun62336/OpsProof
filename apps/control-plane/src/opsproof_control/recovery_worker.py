"""Restricted resume execution and separate, independent outcome verification."""

import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx2 as httpx
from psycopg.types.json import Jsonb

from .config import settings
from .db import pool
from .diagnosis import Snapshot
from .operations import recovery_event
from .shutdown import checkpoint

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 2


def _finish(recovery_id: UUID, status: str, reason: str) -> None:
    with pool().connection() as conn:
        row = conn.execute(
            "UPDATE recoveries SET status=%s,error=%s,completed_at=now() "
            "WHERE id=%s AND status='running' RETURNING id",
            (status, reason[:250], recovery_id),
        ).fetchone()
        if row:
            recovery_event(conn, recovery_id, status, {"reason": reason[:250]})


def execute_next_recovery() -> None:
    with pool().connection() as conn:
        expired = conn.execute(
            "UPDATE recoveries SET status='expired',completed_at=now() "
            "WHERE status IN ('pending_approval','approved') AND expires_at <= now() RETURNING id"
        ).fetchall()
        for item in expired:
            recovery_event(conn, item["id"], "expired")
        row = conn.execute(
            "SELECT * FROM recoveries WHERE status='approved' OR "
            "(status='running' AND started_at < now() - interval '60 seconds') "
            "ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"
        ).fetchone()
        if not row:
            return
        # A crashed worker leaves a durable running record. Retry only this same UUID.
        if row["attempts"] >= MAX_ATTEMPTS:
            conn.execute(
                "UPDATE recoveries SET status='indeterminate', completed_at=now(), "
                "error='Actuator response not established within retry bound' WHERE id=%s",
                (row["id"],),
            )
            recovery_event(conn, row["id"], "indeterminate")
            return
        row = conn.execute(
            "UPDATE recoveries SET status='running', started_at=now(), "
            "attempts=attempts+1 WHERE id=%s RETURNING *",
            (row["id"],),
        ).fetchone()
        recovery_event(conn, row["id"], "attempt_started", {"attempt": row["attempts"]})
    recovery_id = row["id"]
    uncertain = "indeterminate" if row["attempts"] > 1 else "failed"
    config = settings()
    if not config.recovery_enabled or row["action"] != "resume_demo_worker":
        _finish(recovery_id, uncertain, "Recovery disabled or action unsupported")
        return
    try:
        with pool().connection() as conn:
            incident = conn.execute(
                "SELECT * FROM incidents WHERE fingerprint=%s", (row["incident_fingerprint"],)
            ).fetchone()
            experiment = conn.execute(
                "SELECT * FROM experiments WHERE id=%s", (row["run_id"],)
            ).fetchone()
            investigation = conn.execute(
                "SELECT * FROM investigations WHERE id=%s", (row["investigation_id"],)
            ).fetchone()
        if datetime.now(UTC) >= row["expires_at"]:
            _finish(recovery_id, "indeterminate", "Approval expired before confirmed action result")
            return
        if (
            not incident
            or incident["status"] != "firing"
            or incident["target"] != "opsproof-demo-api"
            or incident["name"] != "OpsProofDemoQueueBacklog"
            or not experiment
            or experiment["status"] != "verifying"
            or experiment["scenario"] != "queue-burst"
        ):
            _finish(recovery_id, uncertain, "Incident or experiment no longer eligible")
            return
        snapshot = Snapshot.model_validate(investigation["snapshot"])
        if not snapshot.job_ids or len(snapshot.job_ids) != experiment["count"]:
            _finish(recovery_id, uncertain, "Exact linked job evidence missing")
            return
        with httpx.Client(base_url=config.target_url, timeout=5, trust_env=False) as client:
            if row["attempts"] == 1:
                response = client.get(
                    "/api/v1/internal/worker-state",
                    headers={
                        "X-OpsProof-Inspect-Key": config.inspection_key,
                    },
                )
                response.raise_for_status()
                state = response.json()
                if (
                    state.get("paused") is not True
                    or type(state.get("ttl_seconds")) is not int
                    or not 30 < state["ttl_seconds"] <= 480
                ):
                    _finish(recovery_id, "failed", "Fresh bounded worker hold not confirmed")
                    return
            # Expiry is checked again immediately before the actuator request.
            if datetime.now(UTC) >= row["expires_at"]:
                _finish(recovery_id, "indeterminate", "Approval expired before actuator request")
                return
            response = client.post(
                "/api/v1/internal/worker/resume",
                headers={
                    "X-OpsProof-Recovery-Key": config.recovery_key,
                },
                json={"recovery_id": str(recovery_id)},
            )
            response.raise_for_status()
            result = response.json().get("result")
        if result not in ("applied", "replayed"):
            _finish(recovery_id, uncertain, "Actuator did not acknowledge a resume")
            return
        with pool().connection() as conn:
            updated = conn.execute(
                "UPDATE recoveries SET status='verifying', verify_by=now()+interval '120 seconds',"
                "result=%s WHERE id=%s AND status='running' RETURNING id",
                (Jsonb({"actuator": result}), recovery_id),
            ).fetchone()
            if updated:
                recovery_event(conn, recovery_id, "action_acknowledged", {"actuator": result})
    except httpx.TransportError:
        # Outcome may be unknown: leave running for one bounded, authorized replay.
        logger.warning("Actuator transport outcome unknown for %s", recovery_id)
    except Exception as exc:
        _finish(recovery_id, "indeterminate", f"Action result unavailable: {type(exc).__name__}")


def verify_next_recovery() -> None:
    # One observation per record per tick: no blocking wait that starves investigations.
    with pool().connection() as conn:
        rows = conn.execute(
            "SELECT * FROM recoveries WHERE status='verifying' ORDER BY created_at LIMIT 20"
        ).fetchall()
    for row in rows:
        checkpoint()
        with pool().connection() as conn:
            investigation = conn.execute(
                "SELECT snapshot FROM investigations WHERE id=%s", (row["investigation_id"],)
            ).fetchone()
            experiment = conn.execute(
                "SELECT status FROM experiments WHERE id=%s", (row["run_id"],)
            ).fetchone()
            incident = conn.execute(
                "SELECT status,resolved_at FROM incidents WHERE fingerprint=%s",
                (row["incident_fingerprint"],),
            ).fetchone()
        snapshot = Snapshot.model_validate(investigation["snapshot"])
        job_ids = snapshot.job_ids
        statuses: list[str] = []
        hold_cleared = False
        try:
            with httpx.Client(base_url=settings().target_url, timeout=3, trust_env=False) as client:
                for job_id in job_ids:
                    checkpoint()
                    response = client.get(f"/api/v1/jobs/{job_id}")
                    response.raise_for_status()
                    job = response.json()
                    if job.get("id") != str(job_id):
                        raise ValueError("Job identity mismatch")
                    statuses.append(job["status"])
                response = client.get(
                    "/api/v1/internal/worker-state",
                    headers={
                        "X-OpsProof-Inspect-Key": settings().inspection_key,
                    },
                )
                response.raise_for_status()
                hold_cleared = response.json().get("paused") is False
        except httpx.HTTPError, ValueError, KeyError, TypeError:
            pass
        experiment_status = experiment["status"] if experiment else None
        incident_status = incident["status"] if incident else None
        result = {
            **row["result"],
            "worker_hold_cleared": hold_cleared,
            "job_ids": [str(job) for job in job_ids],
            "job_statuses": statuses,
            "experiment_status": experiment_status,
            "incident_status": incident_status,
        }
        terminal = None
        if "failed" in statuses or experiment_status == "failed":
            terminal = "failed"
        elif (
            row["result"].get("actuator") in ("applied", "replayed")
            and hold_cleared
            and job_ids
            and len(statuses) == len(job_ids)
            and all(status == "completed" for status in statuses)
            and experiment_status == "succeeded"
            and incident_status == "resolved"
            and incident["resolved_at"] is not None
            and incident["resolved_at"] >= row["approved_at"]
        ):
            terminal = "succeeded"
        elif datetime.now(UTC) >= row["verify_by"]:
            terminal = "indeterminate"
        with pool().connection() as conn:
            if terminal:
                reason = None if terminal == "succeeded" else "Recovery conditions not established"
                updated = conn.execute(
                    "UPDATE recoveries SET status=%s,result=%s,error=%s,completed_at=now() "
                    "WHERE id=%s AND status='verifying' RETURNING id",
                    (terminal, Jsonb(result), reason, row["id"]),
                ).fetchone()
                if updated:
                    recovery_event(conn, row["id"], terminal, result)
            else:
                conn.execute(
                    "UPDATE recoveries SET result=%s WHERE id=%s AND status='verifying'",
                    (Jsonb(result), row["id"]),
                )
