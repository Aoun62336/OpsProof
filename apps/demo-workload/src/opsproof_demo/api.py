"""HTTP API for creating and inspecting background jobs."""

from secrets import compare_digest
from uuid import UUID, uuid4

import redis
from fastapi import Depends, FastAPI, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict

from .config import settings
from .contracts import CreateJob, JobCounts, JobDetails
from .db import pool
from .m6_probe import probe as probe_database
from .metrics import install_metrics
from .worker_control import hold_state, resume_worker

app = FastAPI(
    title="OpsProof Demo Workload",
    version="0.1.0",
)


class ResumeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    recovery_id: UUID


def require_inspection(x_opsproof_inspect_key: str | None = Header(default=None)) -> None:
    expected = settings().inspection_key
    if not expected or not compare_digest(x_opsproof_inspect_key or "", expected):
        raise HTTPException(status_code=401, detail="Inspection key required")


def require_recovery(x_opsproof_recovery_key: str | None = Header(default=None)) -> None:
    expected = settings().recovery_key
    if not expected or not compare_digest(x_opsproof_recovery_key or "", expected):
        raise HTTPException(status_code=401, detail="Recovery key required")


@app.get("/api/v1/internal/worker-state", dependencies=[Depends(require_inspection)])
def worker_state() -> dict[str, bool | int]:
    with redis.Redis.from_url(settings().redis_url, socket_timeout=3) as client:
        return hold_state(client)


@app.get("/api/v1/internal/dependency-probe", dependencies=[Depends(require_inspection)])
def dependency_probe() -> dict:
    return probe_database(settings())


@app.post("/api/v1/internal/worker/resume", dependencies=[Depends(require_recovery)])
def worker_resume(payload: ResumeBody) -> dict[str, str]:
    with redis.Redis.from_url(settings().redis_url, socket_timeout=3) as client:
        return {"result": resume_worker(client, payload.recovery_id)}


install_metrics(app)


@app.get("/health/live")
def live() -> dict[str, str]:
    return {"status": "alive"}


@app.get("/health/ready")
def ready() -> dict[str, str]:
    try:
        with pool().connection() as conn:
            conn.execute("SELECT 1")

        redis.Redis.from_url(
            settings().redis_url,
            socket_timeout=2,
        ).ping()

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="dependency unavailable",
        ) from exc

    return {"status": "ready"}


@app.post(
    "/api/v1/jobs",
    response_model=JobDetails,
    status_code=status.HTTP_202_ACCEPTED,
)
def create_job(
    payload: CreateJob,
    idempotency_key: str = Header(
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9._:-]+$",
    ),
) -> JobDetails:
    job_id = uuid4()

    with pool().connection() as conn:
        row = conn.execute(
            """
            INSERT INTO jobs (
                id,
                idempotency_key,
                duration_ms
            )
            VALUES (%s, %s, %s)
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING *
            """,
            (
                job_id,
                idempotency_key,
                payload.duration_ms,
            ),
        ).fetchone()

        if row is None:
            row = conn.execute(
                """
                SELECT *
                FROM jobs
                WHERE idempotency_key = %s
                """,
                (idempotency_key,),
            ).fetchone()

            if row is None:
                raise HTTPException(
                    status_code=409,
                    detail="idempotency conflict",
                )

            if row["duration_ms"] != payload.duration_ms:
                raise HTTPException(
                    status_code=409,
                    detail="idempotency key reused",
                )

        else:
            conn.execute(
                """
                INSERT INTO outbox (job_id)
                VALUES (%s)
                """,
                (job_id,),
            )

    return JobDetails.model_validate(row)


@app.get(
    "/api/v1/jobs/{job_id}",
    response_model=JobDetails,
)
def job_details(job_id: UUID) -> JobDetails:
    with pool().connection() as conn:
        row = conn.execute(
            "SELECT * FROM jobs WHERE id = %s",
            (job_id,),
        ).fetchone()

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="job not found",
        )

    return JobDetails.model_validate(row)


@app.get(
    "/api/v1/stats",
    response_model=JobCounts,
)
def stats() -> JobCounts:
    with pool().connection() as conn:
        row = conn.execute(
            """
            SELECT
                count(*) FILTER (
                    WHERE status = 'queued'
                ) AS queued,

                count(*) FILTER (
                    WHERE status = 'processing'
                ) AS processing,

                count(*) FILTER (
                    WHERE status = 'completed'
                ) AS completed,

                count(*) FILTER (
                    WHERE status = 'failed'
                ) AS failed
            FROM jobs
            """
        ).fetchone()

    return JobCounts.model_validate(row)
