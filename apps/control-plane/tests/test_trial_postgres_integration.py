"""Optional genuine PostgreSQL trial-store test.

Explicitly requires OPSPROOF_M6_TEST_DATABASE_URL, a disposable local test DB
that has already been migrated through revision 0007. Never uses M5 credentials.
"""

import os
from urllib.parse import urlparse
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row

from opsproof_control.trial_catalog import Scenario
from opsproof_control.trial_store import (
    TrialConflict,
    create_trial,
    events,
    get_trial,
    request_abort,
)


def _test_dsn() -> str:
    dsn = os.getenv("OPSPROOF_M6_TEST_DATABASE_URL", "")
    if not dsn:
        pytest.skip("No explicitly configured disposable M6 PostgreSQL test database")
    parsed = urlparse(dsn)
    if parsed.hostname != "127.0.0.1" or parsed.port != 15432 or parsed.path != "/opsproof_m6_test":
        pytest.fail("M6 integration DB must be local port 15432 and named opsproof_m6_test")
    return dsn


def test_real_pg_idempotency_target_conflict_and_terminal_audit():
    dsn = _test_dsn()
    key = f"m6-db-test-{uuid4().hex}"
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()
        assert version["version_num"] == "0007", "Run Alembic revision 0007 first"
        trial, is_new = create_trial(
            conn,
            request_key=key,
            scenario=Scenario.WORKER_FAILURE,
            source_revision="38b3a46",
        )
        assert is_new
        same, created = create_trial(
            conn,
            request_key=key,
            scenario=Scenario.WORKER_FAILURE,
            source_revision="38b3a46",
        )
        assert not created and same["id"] == trial["id"]
        with pytest.raises(TrialConflict):
            create_trial(
                conn,
                request_key=f"other-{uuid4().hex}",
                scenario=Scenario.WORKER_SATURATION,
                source_revision="38b3a46",
            )
        assert get_trial(conn, trial["id"])["phase"] == "requested"
        result = request_abort(conn, trial["id"])
        assert result["phase"] == "aborted"
        kinds = [row["kind"] for row in events(conn, trial["id"])]
        assert "requested" in kinds and "phase:aborted" in kinds
        with pytest.raises(psycopg.errors.RaiseException):
            with conn.transaction():
                conn.execute("DELETE FROM m6_trial_events WHERE trial_id=%s", (trial["id"],))
