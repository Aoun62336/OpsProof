"""Opt-in authenticated fresh-connection observation for the local database fault.

Existing pooled TCP sessions can survive a NetworkPolicy update. This bounded
read-only probe observes a new connection without terminating business sessions.
"""

from datetime import UTC, datetime
from threading import BoundedSemaphore

import psycopg
from fastapi import HTTPException
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from psycopg.conninfo import conninfo_to_dict

LIMIT = BoundedSemaphore(2)
HOSTS = {"demo-deps-postgres", "demo-deps-postgres.opsproof-demo.svc.cluster.local"}


def probe(config):
    if not getattr(config, "m6_dependency_probe_enabled", False):
        raise HTTPException(status_code=404, detail="M6 dependency probe is disabled")
    fields = conninfo_to_dict(config.database_url)
    if (
        fields.get("host") not in HOSTS
        or fields.get("port", "5432") != "5432"
        or fields.get("dbname") != "opsproof"
        or fields.get("hostaddr")
        or fields.get("service")
    ):
        raise HTTPException(status_code=409, detail="M6 requires the fixed local demo database")
    if not LIMIT.acquire(blocking=False):
        raise HTTPException(status_code=503, detail="M6 probe capacity unavailable")
    try:
        with trace.get_tracer(__name__).start_as_current_span(
            "opsproof.database.probe",
            kind=SpanKind.CLIENT,
            attributes={
                "db.system": "postgresql",
                "server.address": "demo-deps-postgres",
                "db.namespace": "opsproof",
            },
        ):
            with psycopg.connect(
                config.database_url,
                connect_timeout=1,
                tcp_user_timeout=1000,
                options="-c default_transaction_read_only=on -c statement_timeout=1000",
            ) as conn:
                conn.execute("SELECT 1")
        return {"ready": True, "connection": "fresh", "observed_at": datetime.now(UTC).isoformat()}
    except (psycopg.Error, OSError) as exc:
        raise HTTPException(
            status_code=503, detail="Fresh database connection unavailable"
        ) from exc
    finally:
        LIMIT.release()
