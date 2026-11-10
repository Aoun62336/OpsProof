"""Redis Streams worker with PostgreSQL fencing and retries."""

import logging
import os
import time
from uuid import UUID, uuid4

from redis import Redis
from redis.exceptions import ResponseError

from .config import settings
from .db import pool
from .downstream import probe
from .shutdown import checkpoint, stopping
from .worker_control import HOLD_KEY

logger = logging.getLogger(__name__)


def process_entry(
    redis_client: Redis,
    message_id: str,
    data: dict[str, str],
) -> None:
    config = settings()

    job_id = UUID(data["job_id"])
    token = uuid4()

    should_ack = False
    duration_ms: int | None = None

    with pool().connection() as conn:
        row = conn.execute(
            """
            SELECT status, attempts, lease_until
            FROM jobs
            WHERE id = %s
            FOR UPDATE
            """,
            (job_id,),
        ).fetchone()

        if row is None or row["status"] in (
            "completed",
            "failed",
        ):
            should_ack = True

        elif row["status"] == "processing":
            lease_valid = conn.execute(
                """
                SELECT lease_until > now() AS valid
                FROM jobs
                WHERE id = %s
                """,
                (job_id,),
            ).fetchone()["valid"]

            if lease_valid:
                return

        if not should_ack and row is not None:
            if row["attempts"] >= config.max_attempts:
                conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'failed',
                        lease_until = NULL
                    WHERE id = %s
                    """,
                    (job_id,),
                )

                should_ack = True

            else:
                claimed = conn.execute(
                    """
                    UPDATE jobs
                    SET status = 'processing',
                        attempts = attempts + 1,
                        started_at = now(),
                        lease_until = now()
                            + make_interval(secs => %s),
                        worker_token = %s
                    WHERE id = %s
                      AND (
                          status = 'queued'
                          OR (
                              status = 'processing'
                              AND lease_until <= now()
                          )
                      )
                    RETURNING duration_ms
                    """,
                    (
                        config.lease_seconds,
                        token,
                        job_id,
                    ),
                ).fetchone()

                if claimed:
                    duration_ms = claimed["duration_ms"]

    # Acknowledge only after the database transaction commits.
    if should_ack:
        redis_client.xack(
            config.stream_name,
            config.consumer_group,
            message_id,
        )
        return

    if duration_ms is None:
        return

    # Job completion is conditional on the opted-in real downstream dependency.
    # A timeout is deliberately not acknowledged as success; the existing
    # lease/fencing and retry path controls subsequent delivery.
    time.sleep(duration_ms / 1000)
    probe(
        enabled=config.downstream_enabled,
        url=config.downstream_url,
        timeout_ms=config.downstream_timeout_ms,
        attempts=config.downstream_attempts,
    )

    with pool().connection() as conn:
        finished = conn.execute(
            """
            UPDATE jobs
            SET status = 'completed',
                completed_at = now(),
                lease_until = NULL
            WHERE id = %s
              AND status = 'processing'
              AND worker_token = %s
            RETURNING id
            """,
            (job_id, token),
        ).fetchone()

    if finished:
        redis_client.xack(
            config.stream_name,
            config.consumer_group,
            message_id,
        )

        logger.info("completed job %s", job_id)


def run() -> None:
    config = settings()

    redis_client = Redis.from_url(
        config.redis_url,
        decode_responses=True,
        socket_timeout=4,
    )

    consumer = f"{os.getenv('HOSTNAME', 'worker')}-{os.getpid()}"

    group_ready = False

    try:
        while not stopping.is_set():
            try:
                if not group_ready:
                    try:
                        redis_client.xgroup_create(
                            config.stream_name,
                            config.consumer_group,
                            id="0",
                            mkstream=True,
                        )

                    except ResponseError as exc:
                        if "BUSYGROUP" not in str(exc):
                            raise

                    group_ready = True

                if redis_client.get(HOLD_KEY):
                    stopping.wait(0.5)
                    continue

                checkpoint()
                claimed = redis_client.xautoclaim(
                    config.stream_name,
                    config.consumer_group,
                    consumer,
                    min_idle_time=config.lease_seconds * 1000,
                    start_id="0-0",
                    count=4,
                )

                entries = claimed[1]

                checkpoint()
                if not entries:
                    delivered = redis_client.xreadgroup(
                        config.consumer_group,
                        consumer,
                        {config.stream_name: ">"},
                        count=1,
                        block=1500,
                    )

                    entries = delivered[0][1] if delivered else []

                for message_id, fields in entries:
                    checkpoint()
                    while redis_client.get(HOLD_KEY):
                        checkpoint()
                        stopping.wait(0.5)
                    checkpoint()
                    process_entry(
                        redis_client,
                        message_id,
                        fields,
                    )

            except Exception:
                group_ready = False

                logger.exception("worker iteration failed; retrying")

                stopping.wait(1)
    finally:
        redis_client.close()
