"""Redis Streams messaging backed by a PostgreSQL outbox."""

import logging
import os
from collections.abc import Callable
from uuid import UUID

from opentelemetry import trace
from redis import Redis
from redis.exceptions import ResponseError

from .db import pool, redis_client
from .shutdown import checkpoint, stopping
from .telemetry import bounded_context, capture_context, message_span

logger = logging.getLogger(__name__)


def ensure_group(
    redis: Redis,
    stream: str,
    group: str,
) -> None:
    try:
        redis.xgroup_create(
            stream,
            group,
            id="0",
            mkstream=True,
        )
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


def messages(
    redis: Redis,
    stream: str,
    group: str,
    consumer: str,
    lease_ms: int = 30_000,
) -> list[tuple[str, dict[str, str]]]:
    """Return pending abandoned messages first, then new ones."""
    claimed = redis.xautoclaim(
        stream,
        group,
        consumer,
        min_idle_time=lease_ms,
        start_id="0-0",
        count=4,
    )
    entries = claimed[1]

    checkpoint()
    if not entries:
        delivered = redis.xreadgroup(
            group,
            consumer,
            {stream: ">"},
            count=1,
            block=1500,
        )
        entries = delivered[0][1] if delivered else []

    return entries


def dispatcher() -> None:
    """Read the control-plane outbox and publish to Redis Streams."""
    while not stopping.is_set():
        try:
            redis = redis_client()

            with pool().connection() as conn:
                row = conn.execute(
                    """
                    SELECT id, stream, run_id, trace_context
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
                        run_id=row["run_id"],
                    ):
                        redis.xadd(
                            row["stream"],
                            {"run_id": str(row["run_id"]), **capture_context()},
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


def consume(
    stream: str,
    group: str,
    handler: Callable[[UUID], None],
    tick: Callable[[], None] | None = None,
) -> None:
    """Generic consumer loop for a Redis Stream consumer group."""
    redis = redis_client()
    consumer = f"{os.getenv('HOSTNAME', 'worker')}-{os.getpid()}"
    group_ready = False

    while not stopping.is_set():
        try:
            if not group_ready:
                ensure_group(redis, stream, group)
                group_ready = True

            entries = messages(redis, stream, group, consumer)

            for message_id, fields in entries:
                checkpoint()
                run_id = UUID(fields["run_id"])
                try:
                    with message_span("experiments process", fields, run_id=run_id):
                        handler(run_id)
                        redis.xack(stream, group, message_id)
                except Exception:
                    logger.exception(
                        "Handler failed for run %s message %s",
                        run_id,
                        message_id,
                    )

        except Exception:
            group_ready = False
            logger.exception("consumer iteration failed; retrying")
            stopping.wait(1)

        if tick is not None and not stopping.is_set():
            try:
                tick()
            except Exception:
                logger.exception("Secondary durable work failed; retrying")
