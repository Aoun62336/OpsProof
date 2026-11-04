"""Read-only verification of completed sandbox experiments."""

import logging
import time
from uuid import UUID

import httpx

from .config import settings
from .db import pool
from .store import event, fail
from .streams import consume

logger = logging.getLogger(__name__)

VERIFY_TIMEOUT_S = 90
POLL_INTERVAL_S = 2


def verify(run_id: UUID) -> None:
    """Check that all submitted jobs reached the completed state."""
    with pool().connection() as conn:
        row = conn.execute(
            "SELECT * FROM experiments WHERE id = %s",
            (run_id,),
        ).fetchone()

    if row is None:
        return

    if row["status"] not in ("verifying",):
        return

    # Find the job IDs recorded by the action worker
    with pool().connection() as conn:
        ev = conn.execute(
            """
            SELECT details
            FROM experiment_events
            WHERE run_id = %s
              AND type IN ('jobs_processed', 'action_completed')
            ORDER BY id DESC
            LIMIT 1
            """,
            (run_id,),
        ).fetchone()

    if ev is None:
        with pool().connection() as conn:
            fail(conn, run_id, "No jobs_processed event found")
        return

    job_ids: list[str] = ev["details"]["job_ids"]

    try:
        deadline = time.monotonic() + VERIFY_TIMEOUT_S

        with httpx.Client(
            base_url=settings().target_url,
            timeout=5,
            trust_env=False,
        ) as http:
            while True:
                if time.monotonic() > deadline:
                    with pool().connection() as conn:
                        fail(
                            conn,
                            run_id,
                            "Verification timed out waiting for jobs to complete",
                        )
                    return

                statuses = []
                for job_id in job_ids:
                    resp = http.get(f"/api/v1/jobs/{job_id}")
                    resp.raise_for_status()
                    statuses.append(resp.json()["status"])

                completed = sum(1 for s in statuses if s == "completed")
                failed_count = sum(1 for s in statuses if s == "failed")
                pending = sum(1 for s in statuses if s in ("queued", "processing"))

                if pending == 0:
                    break

                time.sleep(POLL_INTERVAL_S)

        new_result = {
            "job_ids": job_ids,
            "total": len(job_ids),
            "submitted": len(job_ids),
            "completed": completed,
            "verified_completed": completed,
            "failed": failed_count,
        }

        with pool().connection() as conn:
            if failed_count > 0:
                fail(
                    conn,
                    run_id,
                    f"{failed_count} of {len(job_ids)} jobs failed",
                )
            else:
                from psycopg.types.json import Jsonb

                conn.execute(
                    """
                    UPDATE experiments
                    SET status = 'succeeded',
                        result = %s,
                        completed_at = now()
                    WHERE id = %s
                    """,
                    (
                        Jsonb(new_result),
                        run_id,
                    ),
                )
                event(
                    conn,
                    run_id,
                    "verified",
                    {"completed": completed},
                )

    except Exception as exc:
        logger.exception(
            "Evidence verification failed for %s",
            run_id,
        )
        with pool().connection() as conn:
            fail(
                conn,
                run_id,
                (f"Evidence verification failed: {type(exc).__name__}"),
            )


def run() -> None:
    consume(
        settings().evidence_stream,
        "evidence-workers",
        verify,
    )
