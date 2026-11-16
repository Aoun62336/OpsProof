"""Real nonowner permissions; owner-trigger tests alone cannot prove isolation."""

import secrets
from uuid import uuid4

import psycopg
import pytest
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from scripts.reliability.data_access import (
    grant_control_application,
    grant_sql_observer,
    revoke_control_application,
    revoke_sql_observer,
)
from test_postgres_safety import connect, sent
from test_postgres_safety import dsn as dsn

from opsproof_control import trial_store as store
from opsproof_control.trial_catalog import Scenario


def test_read_only_sql_observer_cannot_write_or_read_control_tables(dsn):
    username = "m6_read_" + uuid4().hex[:16]
    password = secrets.token_hex(24)
    with connect(dsn) as owner:
        owner.execute("CREATE TABLE IF NOT EXISTS jobs (id uuid,status text)")
        grant_sql_observer(owner, username, password, ["jobs"])
    try:
        with psycopg.connect(make_conninfo(dsn, user=username, password=password)) as reader:
            reader.execute("SELECT id FROM jobs LIMIT 1")
            for statement in (
                "UPDATE jobs SET status=status WHERE false",
                "SELECT * FROM m6_trials",
                "CREATE TABLE forbidden_observer_ddl (id int)",
            ):
                with pytest.raises(psycopg.errors.InsufficientPrivilege), reader.transaction():
                    reader.execute(statement)
    finally:
        with connect(dsn) as owner:
            revoke_sql_observer(owner, username, ["jobs"])


def test_nonowner_api_role_can_create_and_abort_but_cannot_forge_proof_or_remove_guards(dsn):
    username = "m6_app_" + uuid4().hex[:16]
    password = secrets.token_hex(24)
    with connect(dsn) as owner:
        grant_control_application(owner, username, password)
    try:
        app_dsn = make_conninfo(dsn, user=username, password=password)
        with psycopg.connect(app_dsn, row_factory=dict_row) as app:
            trial, _ = store.create_trial(
                app,
                request_key="app-role-" + uuid4().hex,
                scenario=Scenario.WORKER_FAILURE,
                source_revision="38b3a46",
            )
            store.claim_preflight(app)
            store.arm_trial(
                app,
                trial["id"],
                approved_scope=True,
                cleanup_confirmed=True,
                confirmation="ARM M6 LOCAL TRIAL",
            )
            store.request_abort(app, trial["id"])
            assert store.get_trial(app, trial["id"])["phase"] == "aborted"
        with connect(dsn) as owner:
            trial, _, _ = sent(owner)
        with psycopg.connect(app_dsn, row_factory=dict_row) as app:
            for statement, params in (
                ("UPDATE m6_trials SET injection_acknowledged=true WHERE id=%s", (trial,)),
                ("UPDATE m6_trials SET independent_verified=true WHERE id=%s", (trial,)),
                ("TRUNCATE m6_trial_events", ()),
                ("DELETE FROM m6_trial_events WHERE trial_id=%s", (trial,)),
                ("ALTER TABLE m6_trial_events DISABLE TRIGGER ALL", ()),
                ("INSERT INTO m6_trial_verifications(trial_id) VALUES (%s)", (trial,)),
                ("UPDATE alembic_version SET version_num='0005'", ()),
            ):
                with pytest.raises(psycopg.errors.InsufficientPrivilege), app.transaction():
                    app.execute(statement, params)
            for table in ("m6_target_leases", "m6_execution_leases"):
                with pytest.raises(psycopg.errors.RaiseException), app.transaction():
                    app.execute(f"DELETE FROM {table} WHERE trial_id=%s", (trial,))
            # Abort after possible send remains allowed, but keeps both reservations.
            assert store.request_abort(app, trial)["phase"] == "indeterminate"
            assert (
                app.execute("SELECT trial_id FROM m6_target_leases").fetchone()["trial_id"] == trial
            )
    finally:
        with connect(dsn) as owner:
            revoke_control_application(owner, username)
