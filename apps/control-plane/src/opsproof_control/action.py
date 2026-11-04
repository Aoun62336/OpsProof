"""Execute explicitly approved operations against the demo sandbox."""

import logging
import time
from uuid import UUID

import httpx

from .config import settings
from .db import pool
from .store import enqueue, event, fail
from .streams import consume

logger = logging.getLogger(__name__)


def execute(run_id: UUID) -> None:
    """Claim and execute one queue-burst experiment."""
    row = None

    with pool().connection() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM experiments
            WHERE id = %s
            FOR UPDATE
            """,
            (run_id,),
        ).fetchone()

        if row is None:
            return

        if row["status"] in ("succeeded", "failed", "verifying"):
            return

        if row["scenario"] != "queue-burst":
            fail(
                conn,
                run_id,
                "Unsupported experiment scenario",
            )
            return

        if row["status"] == "queued":
            conn.execute(
                """
                UPDATE experiments
                SET status = 'running',
                    started_at = now()
                WHERE id = %s
                """,
                (run_id,),
            )
            event(
                conn,
                run_id,
                "started",
                {"scenario": "queue-burst"},
            )

    try:
        started = time.monotonic()
        ids: list[str] = []

        with httpx.Client(
            base_url=settings().target_url,
            timeout=5,
            trust_env=False,
        ) as http:
            response = http.get("/health/ready")
            response.raise_for_status()

            before = http.get("/api/v1/stats")
            before.raise_for_status()

            for index in range(row["count"]):
                idempotency_key = f"opsproof-{run_id}-{index}"
                response = http.post(
                    "/api/v1/jobs",
                    json={"duration_ms": row["duration_ms"]},
                    headers={"Idempotency-Key": idempotency_key},
                )
                response.raise_for_status()
                ids.append(response.json()["id"])

        elapsed_ms = int((time.monotonic() - started) * 1000)

        with pool().connection() as conn:
            conn.execute(
                """
                UPDATE experiments
                SET status = 'verifying'
                WHERE id = %s
                  AND status = 'running'
                """,
                (run_id,),
            )
            event(
                conn,
                run_id,
                "jobs_processed",
                {
                    "job_ids": ids,
                    "submitted": len(ids),
                    "elapsed_ms": elapsed_ms,
                },
            )
            enqueue(conn, settings().evidence_stream, run_id)

    except Exception as exc:
        logger.exception("Action failed for run %s", run_id)
        with pool().connection() as conn:
            fail(
                conn,
                run_id,
                f"Action failed: {type(exc).__name__}: {exc}",
            )


def run() -> None:
    consume(
        settings().action_stream,
        "action-workers",
        execute,
    )
