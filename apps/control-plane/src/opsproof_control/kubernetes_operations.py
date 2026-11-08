"""Authenticated durable proposals; the API has no Kubernetes credentials."""

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ConfigDict, Field

from .auth import authorize
from .config import settings
from .db import pool
from .kubernetes_policy import ACTION, CONFIRMATION, PolicyDenied, validate
from .operations import KEY

router = APIRouter(prefix="/api/v1/kubernetes", dependencies=[Depends(authorize)])


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["restore_demo_worker"]
    incident_fingerprint: str = Field(min_length=16, max_length=64)
    run_id: UUID


class Approval(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: Literal["APPROVE DEMO WORKER RESTORE"]


def event(conn, recovery_id, kind, details=None):
    conn.execute(
        "INSERT INTO kubernetes_recovery_events (recovery_id,type,details) VALUES (%s,%s,%s)",
        (recovery_id, kind, Jsonb(details or {})),
    )


def enabled():
    if not settings().kubernetes_recovery_enabled:
        raise HTTPException(403, "Kubernetes recovery is disabled")


@router.get("/workloads")
def workloads():
    if not settings().kubernetes_recovery_enabled:
        return {"enabled": False, "observations": []}
    with pool().connection() as conn:
        rows = conn.execute("SELECT * FROM kubernetes_observations").fetchall()
    return {"enabled": True, "observations": rows, "generated_at": datetime.now(UTC)}


@router.get("/recoveries")
def list_recoveries():
    enabled()
    with pool().connection() as conn:
        return conn.execute(
            "SELECT * FROM kubernetes_recoveries ORDER BY created_at DESC LIMIT 50"
        ).fetchall()


@router.get("/recoveries/{recovery_id}/events")
def events(recovery_id: UUID):
    enabled()
    with pool().connection() as conn:
        return conn.execute(
            "SELECT * FROM kubernetes_recovery_events WHERE recovery_id=%s ORDER BY id",
            (recovery_id,),
        ).fetchall()


def context(conn, row):
    observation = conn.execute(
        "SELECT * FROM kubernetes_observations WHERE name='demo-worker'"
    ).fetchone()
    if not observation or (datetime.now(UTC) - observation["observed_at"]).total_seconds() > 15:
        raise HTTPException(409, "Fresh independent Kubernetes observation required")
    incident = conn.execute(
        "SELECT * FROM incidents WHERE fingerprint=%s", (row["incident_fingerprint"],)
    ).fetchone()
    experiment = conn.execute("SELECT * FROM experiments WHERE id=%s", (row["run_id"],)).fetchone()
    return observation, incident, experiment


@router.post("/recoveries", status_code=202)
def propose(payload: Proposal, idempotency_key: str = KEY):
    enabled()
    with pool().connection() as conn:
        old = conn.execute(
            "SELECT * FROM kubernetes_recoveries WHERE request_key=%s", (idempotency_key,)
        ).fetchone()
        if old:
            if (
                old["action"] != payload.action
                or old["run_id"] != payload.run_id
                or old["incident_fingerprint"] != payload.incident_fingerprint
            ):
                raise HTTPException(409, "Idempotency payload conflict")
            return old
        observation, incident, experiment = context(conn, payload.model_dump())
        target = observation["resource"]
        now = datetime.now(UTC)
        row = dict(
            id=uuid4(),
            action=ACTION,
            run_id=payload.run_id,
            incident_fingerprint=payload.incident_fingerprint,
            target_uid=target["metadata"]["uid"],
            target_version=target["metadata"]["resourceVersion"],
            target_image=target["spec"]["template"]["spec"]["containers"][0]["image"],
            expires_at=now + timedelta(seconds=120),
        )
        # This is an eligibility check only, not approval or execution authority.
        try:
            validate(
                {**row, "status": "running", "approved_at": now},
                target,
                observation["telemetry"],
                incident,
                experiment,
            )
        except PolicyDenied as exc:
            raise HTTPException(409, str(exc)) from exc
        jobs = conn.execute(
            "SELECT details FROM experiment_events WHERE run_id=%s AND "
            "type='jobs_processed' ORDER BY id DESC LIMIT 1",
            (payload.run_id,),
        ).fetchone()
        ids = jobs["details"].get("job_ids", []) if jobs else []
        if not ids or len(set(ids)) != len(ids) or len(ids) != experiment["count"] or len(ids) > 8:
            raise HTTPException(409, "Exact bounded experiment jobs required")
        saved = conn.execute(
            """INSERT INTO kubernetes_recoveries
          (id,request_key,action,incident_fingerprint,run_id,status,target_uid,target_version,target_image,job_ids,expires_at)
          VALUES (%s,%s,%s,%s,%s,'pending_approval',%s,%s,%s,%s,%s) RETURNING *""",
            (
                row["id"],
                idempotency_key,
                ACTION,
                payload.incident_fingerprint,
                payload.run_id,
                row["target_uid"],
                row["target_version"],
                row["target_image"],
                Jsonb(ids),
                row["expires_at"],
            ),
        ).fetchone()
        event(
            conn,
            row["id"],
            "proposed",
            {
                "target": "opsproof-demo/Deployment/demo-worker",
                "from_replicas": 0,
                "to_replicas": 1,
            },
        )
        return saved


@router.post("/recoveries/{recovery_id}/approve")
def approve(recovery_id: UUID, payload: Approval):
    enabled()
    with pool().connection() as conn:
        row = conn.execute(
            "SELECT * FROM kubernetes_recoveries WHERE id=%s FOR UPDATE", (recovery_id,)
        ).fetchone()
        if not row or row["status"] != "pending_approval" or payload.confirmation != CONFIRMATION:
            raise HTTPException(409, "Pending proposal required; approval cannot be replayed")
        observation, incident, experiment = context(conn, row)
        now = datetime.now(UTC)
        try:
            validate(
                {**row, "status": "running", "approved_at": now},
                observation["resource"],
                observation["telemetry"],
                incident,
                experiment,
            )
        except PolicyDenied as exc:
            raise HTTPException(409, str(exc)) from exc
        row = conn.execute(
            "UPDATE kubernetes_recoveries SET status='approved',approved_at=now() WHERE "
            "id=%s RETURNING *",
            (recovery_id,),
        ).fetchone()
        event(conn, recovery_id, "approved")
        return row
