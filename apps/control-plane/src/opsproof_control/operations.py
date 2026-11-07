"""Authenticated investigations and operator-governed demo recovery."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from psycopg.errors import UniqueViolation
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .auth import authorize
from .config import settings
from .db import pool
from .diagnosis import Diagnosis, Snapshot, allowed_recovery

router = APIRouter(
    prefix="/api/v1", tags=["Investigations and recovery"], dependencies=[Depends(authorize)]
)
KEY = Header(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")


class InvestigationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    incident_fingerprint: str = Field(min_length=16, max_length=64)
    run_id: UUID | None = None


class RecoveryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    investigation_id: UUID


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: Literal["APPROVE DEMO WORKER RESUME"]


def recovery_event(conn, recovery_id: UUID, kind: str, details: dict | None = None) -> None:
    conn.execute(
        "INSERT INTO recovery_events (recovery_id,type,details) VALUES (%s,%s,%s)",
        (recovery_id, kind, Jsonb(details or {})),
    )


def require_recovery() -> None:
    if not settings().recovery_enabled:
        raise HTTPException(status_code=403, detail="Recovery is disabled")


def eligible(conn, investigation: dict | None) -> None:
    if not investigation or investigation["status"] != "ready":
        raise HTTPException(status_code=409, detail="Completed investigation required")
    snapshot = Snapshot.model_validate(investigation["snapshot"])
    baseline = Diagnosis.model_validate(investigation["baseline"])
    allowed, reason = allowed_recovery(snapshot, baseline)
    if not allowed:
        raise HTTPException(status_code=409, detail=reason)
    incident = conn.execute(
        "SELECT * FROM incidents WHERE fingerprint=%s", (investigation["incident_fingerprint"],)
    ).fetchone()
    run = conn.execute(
        "SELECT * FROM experiments WHERE id=%s", (investigation["run_id"],)
    ).fetchone()
    if (
        not incident
        or incident["status"] != "firing"
        or incident["name"] != snapshot.alert_name
        or incident["target"] != snapshot.target
        or not run
        or run["status"] != "verifying"
        or run["scenario"] != "queue-burst"
        or snapshot.run_id != run["id"]
        or len(snapshot.job_ids) != run["count"]
    ):
        raise HTTPException(status_code=409, detail="Incident or experiment no longer eligible")


@router.get("/capabilities")
def capabilities() -> dict:
    s = settings()
    return {
        "recovery_enabled": s.recovery_enabled,
        "ai_enabled": s.ai_enabled,
        "ai_provider": s.ai_provider,
    }


@router.post("/investigations", status_code=202)
def create_investigation(payload: InvestigationRequest, idempotency_key: str = KEY) -> dict:
    with pool().connection() as conn:
        incident = conn.execute(
            "SELECT fingerprint FROM incidents WHERE fingerprint=%s",
            (payload.incident_fingerprint,),
        ).fetchone()
        if not incident:
            raise HTTPException(status_code=404, detail="Incident not found")
        if (
            payload.run_id
            and not conn.execute(
                "SELECT id FROM experiments WHERE id=%s", (payload.run_id,)
            ).fetchone()
        ):
            raise HTTPException(status_code=404, detail="Experiment not found")
        row = conn.execute(
            "INSERT INTO investigations (id,request_key,incident_fingerprint,run_id) "
            "VALUES (%s,%s,%s,%s) ON CONFLICT (request_key) DO NOTHING RETURNING *",
            (uuid4(), idempotency_key, payload.incident_fingerprint, payload.run_id),
        ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT * FROM investigations WHERE request_key=%s", (idempotency_key,)
            ).fetchone()
            if (
                row["incident_fingerprint"] != payload.incident_fingerprint
                or row["run_id"] != payload.run_id
            ):
                raise HTTPException(status_code=409, detail="Idempotency payload conflict")
    return row


@router.get("/investigations")
def list_investigations(incident_fingerprint: str = Query(min_length=16, max_length=64)) -> list:
    with pool().connection() as conn:
        return conn.execute(
            "SELECT * FROM investigations WHERE incident_fingerprint=%s "
            "ORDER BY created_at DESC LIMIT 50",
            (incident_fingerprint,),
        ).fetchall()


@router.post("/investigations/{investigation_id}/ai", status_code=202)
def queue_ai(investigation_id: UUID) -> dict:
    if not settings().ai_enabled:
        raise HTTPException(status_code=403, detail="AI is disabled")
    with pool().connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (74021441,))
        row = conn.execute(
            "SELECT * FROM investigations WHERE id=%s FOR UPDATE", (investigation_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Investigation not found")
        if row["status"] != "ready":
            raise HTTPException(status_code=409, detail="Completed investigation required")
        if row["ai_status"] != "not_requested":
            return row
        count = conn.execute(
            "SELECT count(*) AS n FROM investigations WHERE ai_requested_at >= "
            "(date_trunc('day', now() AT TIME ZONE 'UTC') AT TIME ZONE 'UTC')"
        ).fetchone()["n"]
        if count >= settings().ai_daily_limit:
            raise HTTPException(status_code=429, detail="Daily model request limit reached")
        return conn.execute(
            "UPDATE investigations SET ai_status='queued', ai_requested_at=now() "
            "WHERE id=%s RETURNING *",
            (investigation_id,),
        ).fetchone()


@router.post("/recoveries", status_code=202)
def propose_recovery(payload: RecoveryRequest, idempotency_key: str = KEY) -> dict:
    require_recovery()
    try:
        with pool().connection() as conn:
            # Serialize proposal idempotency and active-incident decisions.
            conn.execute("SELECT pg_advisory_xact_lock(%s)", (74021442,))
            existing = conn.execute(
                "SELECT * FROM recoveries WHERE request_key=%s", (idempotency_key,)
            ).fetchone()
            if existing:
                if existing["investigation_id"] != payload.investigation_id:
                    raise HTTPException(status_code=409, detail="Idempotency payload conflict")
                return existing
            investigation = conn.execute(
                "SELECT * FROM investigations WHERE id=%s", (payload.investigation_id,)
            ).fetchone()
            eligible(conn, investigation)
            row = conn.execute(
                "INSERT INTO recoveries (id,request_key,investigation_id,incident_fingerprint,"
                "run_id,action,expires_at) VALUES (%s,%s,%s,%s,%s,'resume_demo_worker',%s) "
                "RETURNING *",
                (
                    uuid4(),
                    idempotency_key,
                    payload.investigation_id,
                    investigation["incident_fingerprint"],
                    investigation["run_id"],
                    datetime.now(UTC) + timedelta(seconds=120),
                ),
            ).fetchone()
            recovery_event(conn, row["id"], "proposed")
            return row
    except UniqueViolation as exc:
        raise HTTPException(status_code=409, detail="Active recovery already exists") from exc


@router.get("/recoveries")
def list_recoveries() -> list:
    with pool().connection() as conn:
        return conn.execute("SELECT * FROM recoveries ORDER BY created_at DESC LIMIT 50").fetchall()


@router.post("/recoveries/{recovery_id}/approve")
def approve_recovery(recovery_id: UUID, payload: Approval) -> dict:
    require_recovery()
    with pool().connection() as conn:
        row = conn.execute(
            "SELECT * FROM recoveries WHERE id=%s FOR UPDATE", (recovery_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Recovery not found")
        if row["status"] != "pending_approval" or datetime.now(UTC) >= row["expires_at"]:
            raise HTTPException(
                status_code=409, detail="Recovery no longer awaiting valid approval"
            )
        investigation = conn.execute(
            "SELECT * FROM investigations WHERE id=%s", (row["investigation_id"],)
        ).fetchone()
        eligible(conn, investigation)
        row = conn.execute(
            "UPDATE recoveries SET status='approved', approved_at=now() WHERE id=%s RETURNING *",
            (recovery_id,),
        ).fetchone()
        recovery_event(conn, recovery_id, "approved")
        return row


@router.post("/recoveries/{recovery_id}/reject")
def reject_recovery(recovery_id: UUID) -> dict:
    with pool().connection() as conn:
        row = conn.execute(
            "SELECT * FROM recoveries WHERE id=%s FOR UPDATE", (recovery_id,)
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Recovery not found")
        if row["status"] == "rejected":
            return row
        if row["status"] != "pending_approval":
            raise HTTPException(status_code=409, detail="Recovery no longer awaiting approval")
        row = conn.execute(
            "UPDATE recoveries SET status='rejected', completed_at=now() WHERE id=%s RETURNING *",
            (recovery_id,),
        ).fetchone()
        recovery_event(conn, recovery_id, "rejected")
        return row


@router.get("/recoveries/{recovery_id}/events")
def recovery_events(recovery_id: UUID) -> list:
    with pool().connection() as conn:
        return conn.execute(
            "SELECT id,type,details,created_at FROM recovery_events "
            "WHERE recovery_id=%s ORDER BY id LIMIT 200",
            (recovery_id,),
        ).fetchall()
