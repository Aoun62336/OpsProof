"""Read-only verification of completed sandbox experiments."""

import logging
import time
from uuid import UUID

import httpx2 as httpx

from .config import settings
from .db import pool
from .evidence_contracts import exact_job_status, required_job_ids
from .shutdown import ShutdownRequested, checkpoint, stopping
from .store import event, fail
from .streams import consume

logger = logging.getLogger(__name__)

VERIFY_TIMEOUT_S = 240
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

    try:
        job_ids = required_job_ids(ev["details"] if ev else None, row["count"])
    except ValueError as exc:
        with pool().connection() as conn:
            fail(conn, run_id, f"Invalid submitted-job evidence: {exc}")
        return

    try:
        deadline = time.monotonic() + VERIFY_TIMEOUT_S

        with httpx.Client(
            base_url=settings().target_url,
            timeout=5,
            trust_env=False,
        ) as http:
            while True:
                checkpoint()
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
                    checkpoint()
                    resp = http.get(f"/api/v1/jobs/{job_id}")
                    resp.raise_for_status()
                    statuses.append(exact_job_status(resp.json(), job_id))

                completed = sum(1 for s in statuses if s == "completed")
                failed_count = sum(1 for s in statuses if s == "failed")
                pending = sum(1 for s in statuses if s in ("queued", "processing"))

                if pending == 0:
                    break

                stopping.wait(POLL_INTERVAL_S)

        new_result = {
            "job_ids": job_ids,
            "total": len(job_ids),
            "submitted": len(job_ids),
            "completed": completed,
            "verified_completed": completed,
            "failed": failed_count,
        }

        with pool().connection() as conn:
            if failed_count > 0 or completed != len(job_ids):
                fail(
                    conn,
                    run_id,
                    f"Exact-job verification unsuccessful: {completed} completed, "
                    f"{failed_count} failed of {len(job_ids)} expected",
                )
            else:
                from psycopg.types.json import Jsonb

                updated = conn.execute(
                    """
                    UPDATE experiments
                    SET status = 'succeeded',
                        result = %s,
                        completed_at = now()
                    WHERE id = %s AND status = 'verifying'
                    RETURNING id
                    """,
                    (
                        Jsonb(new_result),
                        run_id,
                    ),
                ).fetchone()
                if updated:
                    event(conn, run_id, "verified", {"completed": completed})

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
    """Keep incident review responsive while experiment verification waits."""
    from threading import Thread

    from .investigation_worker import process_next_investigation
    from .kubernetes_worker import observe_and_verify
    from .recovery_worker import verify_next_recovery

    def review_loop() -> None:
        while not stopping.is_set():
            try:
                process_next_investigation()
                checkpoint()
                verify_next_recovery()
                observe_and_verify()
            except ShutdownRequested:
                return
            except Exception:
                logger.exception("Investigation/recovery verification tick failed")
            stopping.wait(1)

    review = Thread(target=review_loop, name="evidence-review")
    review.start()
    try:
        consume(
            settings().evidence_stream,
            "evidence-workers",
            verify,
        )
    finally:
        stopping.set()
        review.join()
