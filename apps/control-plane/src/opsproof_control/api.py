"""Authenticated OpsProof control API."""

import secrets
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.security import APIKeyHeader

from .config import settings
from .contracts import CreateRun, EventView, RunView
from .db import pool, redis_client
from .store import enqueue, event

app = FastAPI(
    title="OpsProof Control API",
    version="0.1.0",
)

api_key_header = APIKeyHeader(
    name="X-OpsProof-Key",
    auto_error=False,
)


def authorize(
    key: str | None = Depends(api_key_header),
) -> None:
    expected = settings().api_key
    if not expected or not key or not secrets.compare_digest(key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )


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
) -> list[RunView]:
    with pool().connection() as conn:
        rows = conn.execute(
            "SELECT * FROM experiments ORDER BY created_at DESC LIMIT %s",
            (limit,),
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
            """,
            (run_id,),
        ).fetchall()

    return [EventView.model_validate(r) for r in rows]
