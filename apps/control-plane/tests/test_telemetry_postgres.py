"""Telemetry migration constraints and metric queries against the guarded real database."""

from contextlib import contextmanager
from time import time
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from test_trial_postgres_integration import _test_dsn

from opsproof_control import metrics


def test_outbox_accepts_legacy_context_and_rejects_nonobject_or_unbounded_data():
    with psycopg.connect(_test_dsn()) as conn:
        run = uuid4()
        conn.execute(
            "INSERT INTO experiments(id,request_key,scenario,count,duration_ms) "
            "VALUES (%s,%s,'queue-burst',1,50)",
            (run, "telemetry-" + str(run)),
        )
        row = conn.execute(
            "INSERT INTO outbox(stream,run_id) VALUES ('test',%s) RETURNING id,trace_context",
            (run,),
        ).fetchone()
        assert row[1] is None
        context = {"traceparent": "00-" + "1" * 32 + "-" + "2" * 16 + "-01"}
        conn.execute("UPDATE outbox SET trace_context=%s WHERE id=%s", (Jsonb(context), row[0]))
        for invalid in (["not-an-object"], {"traceparent": "x" * 1025}):
            with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
                conn.execute(
                    "UPDATE outbox SET trace_context=%s WHERE id=%s", (Jsonb(invalid), row[0])
                )
        assert (
            conn.execute("SELECT trace_context FROM outbox WHERE id=%s", (row[0],)).fetchone()[0]
            == context
        )
        conn.rollback()


def test_durable_age_and_freshness_metrics_execute_real_sql(monkeypatch):
    dsn = _test_dsn()
    run = uuid4()
    with psycopg.connect(dsn) as conn:
        conn.execute(
            "INSERT INTO experiments(id,request_key,scenario,count,duration_ms,created_at) "
            "VALUES (%s,%s,'queue-burst',1,50,now()-interval '90 seconds')",
            (run, "metrics-" + str(run)),
        )

    class Pool:
        @contextmanager
        def connection(self, **_kwargs):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                yield conn

    class Redis:
        def ping(self):
            return True

    monkeypatch.setattr(metrics, "pool", Pool)
    monkeypatch.setattr(metrics, "redis_client", Redis)
    before = time()
    try:
        metrics.refresh_state()
        assert metrics.DEPENDENCIES.labels(dependency="postgresql")._value.get() == 1
        assert metrics.STATE_UPDATED._value.get() >= before
        assert metrics.AGES.labels(state="queued")._value.get() >= 89
    finally:
        with psycopg.connect(dsn) as conn:
            conn.execute("DELETE FROM experiments WHERE id=%s", (run,))
