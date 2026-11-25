"""Authenticated alert ingestion and durable incident records."""

import secrets
from datetime import UTC, datetime
from typing import Literal

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    Query,
    status,
)
from psycopg.types.json import Jsonb
from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
)

from .auth import authorize
from .config import settings
from .db import pool

router = APIRouter(tags=["Incidents"])


class IncomingAlert(BaseModel):
    model_config = ConfigDict(extra="ignore")

    status: Literal["firing", "resolved"]
    fingerprint: str = Field(min_length=16, max_length=64)
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    endsAt: AwareDatetime | None = None


class AlertmanagerWebhook(BaseModel):
    model_config = ConfigDict(extra="ignore")

    alerts: list[IncomingAlert] = Field(default_factory=list)


class IncidentView(BaseModel):
    fingerprint: str
    name: str
    target: str
    severity: str
    summary: str
    status: Literal["firing", "resolved"]
    started_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None = None


class IncidentEventView(BaseModel):
    id: int
    status: Literal["firing", "resolved"]
    created_at: datetime


def verify_webhook_token(
    authorization: str | None = Header(default=None),
) -> None:
    expected_token = settings().alert_webhook_token
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Alert webhook token not configured",
        )

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing alertmanager webhook token",
        )

    token = authorization.removeprefix("Bearer ").strip()
    if not secrets.compare_digest(token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing alertmanager webhook token",
        )


@router.post(
    "/api/v1/internal/alertmanager",
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_webhook_token)],
)
def ingest_alertmanager_webhook(payload: AlertmanagerWebhook) -> dict[str, str | int]:
    now = datetime.now(UTC)

    with pool().connection() as conn:
        # Stable lock order prevents multi-alert batches from deadlocking.
        for alert in sorted(payload.alerts, key=lambda item: item.fingerprint):
            # A row lock cannot serialize first delivery when no row exists yet.
            conn.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                ("opsproof-incident:" + alert.fingerprint,),
            )
            name = alert.labels.get("alertname", "UnknownAlert")
            target = alert.labels.get("job", alert.labels.get("instance", "unknown"))
            severity = alert.labels.get("severity", "warning")
            summary = alert.annotations.get("summary", alert.annotations.get("description", ""))

            row = conn.execute(
                """
                SELECT status, started_at, resolved_at
                FROM incidents
                WHERE fingerprint = %s
                FOR UPDATE
                """,
                (alert.fingerprint,),
            ).fetchone()

            if row is not None:
                if alert.startsAt < row["started_at"]:
                    continue  # Delayed delivery from an older occurrence.
                if (
                    alert.startsAt == row["started_at"]
                    and row["status"] == "resolved"
                    and alert.status == "firing"
                ):
                    continue  # A resolved occurrence cannot be reopened by a retry.
            if alert.status == "resolved" and alert.endsAt is not None:
                if alert.endsAt < alert.startsAt:
                    continue  # Malformed source time cannot resolve an incident.
            if row is None:
                # First observation of this incident
                resolved_at = (alert.endsAt or now) if alert.status == "resolved" else None
                conn.execute(
                    """
                    INSERT INTO incidents (
                        fingerprint,
                        name,
                        target,
                        severity,
                        status,
                        summary,
                        started_at,
                        last_seen_at,
                        resolved_at,
                        payload
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        alert.fingerprint,
                        name,
                        target,
                        severity,
                        alert.status,
                        summary,
                        alert.startsAt,
                        now,
                        resolved_at,
                        Jsonb(alert.model_dump(mode="json")),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO incident_events (
                        incident_fingerprint,
                        status,
                        occurred_at
                    )
                    VALUES (%s, %s, %s)
                    """,
                    (
                        alert.fingerprint,
                        alert.status,
                        resolved_at or alert.startsAt,
                    ),
                )
            else:
                current_status = row["status"]
                if current_status == alert.status and alert.startsAt == row["started_at"]:
                    # Deduplication: state repeated, update observation timestamp only
                    conn.execute(
                        """
                        UPDATE incidents
                        SET last_seen_at = GREATEST(last_seen_at, %s),
                            summary = COALESCE(NULLIF(%s, ''), summary)
                        WHERE fingerprint = %s
                        """,
                        (now, summary, alert.fingerprint),
                    )
                else:
                    # State transition (firing -> resolved or resolved -> firing)
                    resolved_at = (alert.endsAt or now) if alert.status == "resolved" else None
                    conn.execute(
                        """
                        UPDATE incidents
                        SET status = %s,
                            started_at = %s,
                            last_seen_at = GREATEST(last_seen_at, %s),
                            resolved_at = %s,
                            payload = %s,
                            summary = COALESCE(NULLIF(%s, ''), summary)
                        WHERE fingerprint = %s
                        """,
                        (
                            alert.status,
                            alert.startsAt,
                            now,
                            resolved_at,
                            Jsonb(alert.model_dump(mode="json")),
                            summary,
                            alert.fingerprint,
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO incident_events (
                            incident_fingerprint,
                            status,
                            occurred_at
                        )
                        VALUES (%s, %s, %s)
                        """,
                        (
                            alert.fingerprint,
                            alert.status,
                            resolved_at or alert.startsAt,
                        ),
                    )

    return {"status": "ok", "processed": len(payload.alerts)}


@router.get(
    "/api/v1/incidents",
    response_model=list[IncidentView],
    dependencies=[Depends(authorize)],
)
def list_incidents(
    status: Literal["firing", "resolved"] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[IncidentView]:
    with pool().connection() as conn:
        if status:
            rows = conn.execute(
                """
                SELECT
                    fingerprint,
                    name,
                    target,
                    severity,
                    summary,
                    status,
                    started_at,
                    last_seen_at,
                    resolved_at
                FROM incidents
                WHERE status = %s
                ORDER BY started_at DESC
                LIMIT %s OFFSET %s
                """,
                (status, limit, offset),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT
                    fingerprint,
                    name,
                    target,
                    severity,
                    summary,
                    status,
                    started_at,
                    last_seen_at,
                    resolved_at
                FROM incidents
                ORDER BY started_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            ).fetchall()

    return [IncidentView.model_validate(r) for r in rows]


@router.get(
    "/api/v1/incidents/{fingerprint}/events",
    response_model=list[IncidentEventView],
    dependencies=[Depends(authorize)],
)
def get_incident_events(fingerprint: str) -> list[IncidentEventView]:
    with pool().connection() as conn:
        rows = conn.execute(
            """
            SELECT id, status, created_at
            FROM incident_events
            WHERE incident_fingerprint = %s
            ORDER BY id ASC
            LIMIT 100
            """,
            (fingerprint,),
        ).fetchall()

    return [IncidentEventView.model_validate(r) for r in rows]
