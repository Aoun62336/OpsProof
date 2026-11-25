"""Publish committed PostgreSQL outbox events to Redis Streams."""

import logging

from opentelemetry import trace
from redis import Redis

from .config import settings
from .db import pool
from .shutdown import stopping
from .telemetry import bounded_context, capture_context, message_span

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
                        SELECT id, job_id, trace_context
                        FROM outbox
                        WHERE published_at IS NULL
                        ORDER BY id
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                        """
                    ).fetchone()

                    if row:
                        with message_span(
                            "outbox publish",
                            bounded_context(row.get("trace_context")),
                            kind=trace.SpanKind.PRODUCER,
                            job_id=row["job_id"],
                        ):
                            redis_client.xadd(
                                config.stream_name,
                                {"job_id": str(row["job_id"]), **capture_context()},
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
