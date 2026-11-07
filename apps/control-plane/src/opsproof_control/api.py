"""Authenticated experiment APIs backed by durable control-plane state."""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    status,
)
from pydantic import BaseModel

from .auth import authorize
from .auth import router as auth_router
from .config import settings
from .contracts import (
    CreateRun,
    EventView,
    RunStatus,
    RunView,
)
from .db import pool, redis_client
from .incidents import router as incident_router
from .metrics import install_metrics
from .operations import router as operations_router
from .store import enqueue, event

app = FastAPI(
    title="OpsProof Control API",
    version="0.2.0",
)

install_metrics(app)

app.include_router(auth_router)
app.include_router(incident_router)
app.include_router(operations_router)


class SummaryView(BaseModel):
    total: int
    counts: dict[RunStatus, int]
    recent: list[RunView]
    generated_at: str


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    try:
        with pool().connection() as conn:
            conn.execute("SELECT 1")
        redis_client().ping()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="dependency unavailable",
        ) from exc
    return {"status": "ready"}


@app.get(
    "/api/v1/summary",
    response_model=SummaryView,
    dependencies=[Depends(authorize)],
)
def get_summary() -> SummaryView:
    with pool().connection() as conn:
        total_row = conn.execute("SELECT COUNT(*) AS n FROM experiments").fetchone()
        total = total_row["n"] if total_row else 0

        status_rows = conn.execute(
            """
            SELECT status, COUNT(*) AS n
            FROM experiments
            GROUP BY status
            """
        ).fetchall()

        recent_rows = conn.execute(
            """
            SELECT * FROM experiments
            ORDER BY created_at DESC
            LIMIT 10
            """
        ).fetchall()

    counts: dict[RunStatus, int] = {
        "queued": 0,
        "running": 0,
        "verifying": 0,
        "succeeded": 0,
        "failed": 0,
    }
    for row in status_rows:
        s = row["status"]
        if s in counts:
            counts[s] = row["n"]

    return SummaryView(
        total=total,
        counts=counts,
        recent=[RunView.model_validate(r) for r in recent_rows],
        generated_at=datetime.now(UTC).isoformat(),
    )


@app.post(
    "/api/v1/experiments",
    response_model=RunView,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(authorize)],
)
@app.post(
    "/api/v1/runs",
    response_model=RunView,
    status_code=status.HTTP_202_ACCEPTED,
    dependencies=[Depends(authorize)],
)
def create_run(
    payload: CreateRun,
    idempotency_key: str = Header(
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
) -> RunView:
    run_id = uuid4()

    with pool().connection() as conn:
        row = conn.execute(
            """
            INSERT INTO experiments (
                id,
                request_key,
                scenario,
                count,
                duration_ms
            )
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (request_key) DO NOTHING
            RETURNING *
            """,
            (
                run_id,
                idempotency_key,
                payload.scenario,
                payload.count,
                payload.duration_ms,
            ),
        ).fetchone()

        if row is None:
            # Idempotency hit — fetch the existing record
            row = conn.execute(
                "SELECT * FROM experiments WHERE request_key = %s",
                (idempotency_key,),
            ).fetchone()

            if row is None:
                raise HTTPException(
                    status_code=409,
                    detail="idempotency conflict",
                )

            if (
                row["scenario"] != payload.scenario
                or row["count"] != payload.count
                or row["duration_ms"] != payload.duration_ms
            ):
                raise HTTPException(
                    status_code=409,
                    detail="idempotency key reused with different payload",
                )
        else:
            enqueue(conn, settings().action_stream, run_id)
            event(conn, run_id, "created", {"scenario": payload.scenario})

    return RunView.model_validate(row)


@app.get(
    "/api/v1/experiments/{run_id}",
    response_model=RunView,
    dependencies=[Depends(authorize)],
)
@app.get(
    "/api/v1/runs/{run_id}",
    response_model=RunView,
    dependencies=[Depends(authorize)],
)
def get_run(run_id: UUID) -> RunView:
    with pool().connection() as conn:
        row = conn.execute(
            "SELECT * FROM experiments WHERE id = %s",
            (run_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="run not found")

    return RunView.model_validate(row)


@app.get(
    "/api/v1/experiments",
    response_model=list[RunView],
    dependencies=[Depends(authorize)],
)
@app.get(
    "/api/v1/runs",
    response_model=list[RunView],
    dependencies=[Depends(authorize)],
)
def list_runs(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[RunView]:
    with pool().connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM experiments
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
            """,
            (limit, offset),
        ).fetchall()

    return [RunView.model_validate(r) for r in rows]


@app.get(
    "/api/v1/experiments/{run_id}/events",
    response_model=list[EventView],
    dependencies=[Depends(authorize)],
)
@app.get(
    "/api/v1/runs/{run_id}/events",
    response_model=list[EventView],
    dependencies=[Depends(authorize)],
)
def get_run_events(run_id: UUID) -> list[EventView]:
    with pool().connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM experiment_events
            WHERE run_id = %s
            ORDER BY id
            LIMIT 200
            """,
            (run_id,),
        ).fetchall()

    return [EventView.model_validate(r) for r in rows]
