"""Publish committed PostgreSQL outbox events to Redis Streams."""

import logging

from redis import Redis

from .config import settings
from .db import pool
from .shutdown import stopping

logger = logging.getLogger(__name__)


def run() -> None:
    config = settings()

    redis_client = Redis.from_url(
        config.redis_url,
        decode_responses=True,
        socket_timeout=3,
    )

    try:
        while not stopping.is_set():
            try:
                with pool().connection() as conn:
                    row = conn.execute(
                        """
                        SELECT id, job_id
                        FROM outbox
                        WHERE published_at IS NULL
                        ORDER BY id
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                        """
                    ).fetchone()

                    if row:
                        redis_client.xadd(
                            config.stream_name,
                            {"job_id": str(row["job_id"])},
                        )

                        conn.execute(
                            """
                            UPDATE outbox
                            SET published_at = now()
                            WHERE id = %s
                            """,
                            (row["id"],),
                        )

                if row is None:
                    stopping.wait(0.4)

            except Exception:
                logger.exception("outbox dispatch failed; retrying")
                stopping.wait(1)
    finally:
        redis_client.close()
