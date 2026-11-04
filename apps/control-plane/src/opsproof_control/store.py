"""Durable experiment state, audit events and outbox operations."""

from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb


def event(
    conn: Connection,
    run_id: UUID,
    kind: str,
    details: dict,
) -> None:
    conn.execute(
        """
        INSERT INTO experiment_events (
            run_id,
            type,
            details
        )
        VALUES (%s, %s, %s)
        """,
        (
            run_id,
            kind,
            Jsonb(details),
        ),
    )


def enqueue(
    conn: Connection,
    stream: str,
    run_id: UUID,
) -> None:
    conn.execute(
        """
        INSERT INTO outbox (stream, run_id)
        VALUES (%s, %s)
        """,
        (stream, run_id),
    )


def fail(
    conn: Connection,
    run_id: UUID,
    reason: str,
) -> None:
    conn.execute(
        """
        UPDATE experiments
        SET status = 'failed',
            error = %s,
            completed_at = now()
        WHERE id = %s
          AND status NOT IN ('succeeded', 'failed')
        """,
        (reason, run_id),
    )
    event(conn, run_id, "failed", {"reason": reason})
