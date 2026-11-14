"""Disabled-by-default, authenticated M6 trial ledger API.

No endpoint here performs fault injection or accepts self-attested success.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from psycopg import Error as DatabaseError
from psycopg.errors import UniqueViolation
from pydantic import BaseModel, ConfigDict, Field, StrictBool

from .auth import authorize
from .config import settings
from .db import pool
from .m6_access import require_application_role
from .m6_catalog import Scenario
from .m6_trial_store import (
    TrialConflict,
    TrialNotFound,
    arm_trial,
    create_trial,
    events,
    get_trial,
    list_trials,
    request_abort,
)

router = APIRouter(
    prefix="/api/v1/m6/trials",
    tags=["M6 trial ledger"],
    dependencies=[Depends(authorize)],
)


class TrialInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenario: Scenario
    source_revision: str = Field(pattern=r"^[0-9a-f]{7,64}$")


class ArmInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirmation: str
    approved_test_scope: StrictBool
    cleanup_plan_confirmed: StrictBool


class TrialView(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: UUID
    scenario: Scenario
    target: str
    phase: str
    source_revision: str
    approved_test_scope: bool
    cleanup_plan_confirmed: bool
    injection_acknowledged: bool
    independent_verified: bool
    cleanup_verified: bool
    abort_requested: bool
    created_at: datetime
    updated_at: datetime
    approval_expires_at: datetime | None
    error: str | None
    dispatch_intent_at: datetime | None = None
    dispatch_id: UUID | None = None
    dispatch_deadline: datetime | None = None
    target_uid: str | None = None
    target_version: str | None = None


def enabled() -> None:
    if not settings().m6_enabled:
        raise HTTPException(status_code=404, detail="M6 ledger is disabled")
    try:
        with pool().connection() as conn:
            require_application_role(conn)
    except (DatabaseError, PermissionError) as exc:
        raise HTTPException(
            status_code=503, detail="M6 restricted database access is unavailable"
        ) from exc


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, TrialNotFound):
        return HTTPException(status_code=404, detail="Trial not found")
    if isinstance(exc, (TrialConflict, UniqueViolation, ValueError)):
        return HTTPException(status_code=409, detail=str(exc)[:160])
    return HTTPException(status_code=500, detail="Unexpected trial error")


@router.post("", status_code=202, response_model=TrialView)
def create(
    payload: TrialInput,
    idempotency_key: str = Header(min_length=8, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$"),
) -> dict:
    enabled()
    try:
        with pool().connection() as conn:
            row, _new = create_trial(
                conn,
                request_key=idempotency_key,
                scenario=payload.scenario,
                source_revision=payload.source_revision,
            )
            return row
    except (TrialConflict, UniqueViolation, ValueError) as exc:
        raise _http_error(exc) from exc


@router.get("", response_model=list[TrialView])
def index(limit: int = Query(default=30, ge=1, le=100)) -> list[dict]:
    enabled()
    with pool().connection() as conn:
        return list_trials(conn, limit=limit)


@router.get("/{trial_id}", response_model=TrialView)
def detail(trial_id: UUID) -> dict:
    enabled()
    try:
        with pool().connection() as conn:
            return get_trial(conn, trial_id)
    except TrialNotFound as exc:
        raise _http_error(exc) from exc


@router.get("/{trial_id}/events")
def timeline(trial_id: UUID) -> list[dict]:
    enabled()
    try:
        with pool().connection() as conn:
            return events(conn, trial_id)
    except TrialNotFound as exc:
        raise _http_error(exc) from exc


@router.get("/{trial_id}/artifacts")
def artifacts(trial_id: UUID) -> list[dict]:
    enabled()
    try:
        with pool().connection() as conn:
            get_trial(conn, trial_id)
            return conn.execute(
                "SELECT id,kind,relative_path,sha256,created_at,observations "
                "FROM m6_trial_artifacts "
                "WHERE trial_id=%s ORDER BY id",
                (trial_id,),
            ).fetchall()
    except TrialNotFound as exc:
        raise _http_error(exc) from exc


@router.get("/{trial_id}/verifications")
def verifications(trial_id: UUID) -> list[dict]:
    enabled()
    try:
        with pool().connection() as conn:
            get_trial(conn, trial_id)
            return conn.execute(
                "SELECT observer_id,dispatch_id,target_uid,verified_at,cleanup_verified,"
                "hypothesis_verified,report_sha256,observer_sha256,report->'checks' AS checks "
                "FROM m6_trial_verifications WHERE trial_id=%s ORDER BY id",
                (trial_id,),
            ).fetchall()
    except TrialNotFound as exc:
        raise _http_error(exc) from exc


@router.post("/{trial_id}/arm", response_model=TrialView)
def arm(trial_id: UUID, payload: ArmInput) -> dict:
    # Requires an explicit configuration opt-in; no Kubernetes action is wired.
    if not settings().m6_arm_enabled:
        raise HTTPException(status_code=403, detail="M6 arming disabled")
    enabled()
    try:
        with pool().connection() as conn:
            return arm_trial(
                conn,
                trial_id,
                approved_scope=payload.approved_test_scope,
                cleanup_confirmed=payload.cleanup_plan_confirmed,
                confirmation=payload.confirmation,
            )
    except (TrialNotFound, TrialConflict, ValueError) as exc:
        raise _http_error(exc) from exc


@router.post("/{trial_id}/abort", response_model=TrialView)
def abort(trial_id: UUID) -> dict:
    enabled()
    try:
        with pool().connection() as conn:
            return request_abort(conn, trial_id)
    except (TrialNotFound, TrialConflict, ValueError) as exc:
        raise _http_error(exc) from exc
