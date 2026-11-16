"""Real SQL transactions and competing connections; never uses the M5 DB.

Test reset intentionally truncates ONLY M6 tables in the explicitly guarded
disposable database. A skipped suite is not PostgreSQL acceptance.
"""

import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from time import sleep
from uuid import uuid4

import psycopg
import pytest
from psycopg.rows import dict_row
from test_trial_postgres_integration import _test_dsn

from opsproof_control import trial_store as store
from opsproof_control.trial_catalog import Scenario
from opsproof_control.trial_state import TrialPhase


@pytest.fixture
def dsn():
    value = _test_dsn()
    with psycopg.connect(value) as conn:
        conn.execute(
            "TRUNCATE m6_trial_verifications,m6_trial_resolutions,"
            "m6_trial_artifacts,m6_trial_outbox,"
            "m6_execution_leases,m6_target_leases,m6_trial_events,m6_trials RESTART IDENTITY"
        )
    return value


def connect(dsn):
    conn = psycopg.connect(dsn, row_factory=dict_row)
    conn.execute("SET statement_timeout='8s'")
    conn.execute("SET lock_timeout='5s'")
    return conn


def requested(conn, key=None):
    return store.create_trial(
        conn,
        request_key=key or "m6-real-" + uuid4().hex,
        scenario=Scenario.WORKER_FAILURE,
        source_revision="38b3a46",
    )[0]


def armed(conn):
    row = requested(conn)
    assert store.claim_preflight(conn) == row["id"]
    row = store.arm_trial(
        conn,
        row["id"],
        approved_scope=True,
        cleanup_confirmed=True,
        confirmation="ARM M6 LOCAL TRIAL",
    )
    token = conn.execute(
        "SELECT fence_token FROM m6_target_leases WHERE trial_id=%s", (row["id"],)
    ).fetchone()["fence_token"]
    return row["id"], token


def sent(conn):
    trial, token = armed(conn)
    dispatch = store.begin_dispatch(
        conn,
        trial,
        fence_token=token,
        target_uid="real-test-target",
        target_version="101",
        maximum_seconds=120,
    )
    return trial, token, dispatch


def ack(conn, trial, token, dispatch):
    return store.acknowledge_injection(
        conn,
        trial,
        fence_token=token,
        dispatch_id=dispatch,
        receipt_path=f".runtime/m6/test/{trial}/receipt.json",
        receipt_sha256="a" * 64,
    )


def independent_receipt(conn, trial, token, *, hypothesis=True):
    row = store.get_trial(conn, trial)
    proof = {
        "trial_id": str(trial),
        "dispatch_id": str(row["dispatch_id"]),
        "observer_id": str(uuid4()),
        "target_uid": row["target_uid"],
        "verified_at": store._db_now(conn).isoformat(),
        "observer_sha256": "c" * 64,
        "cleanup_verified": True,
        "hypothesis_verified": hypothesis,
        "checks": {
            "current_health": True,
            "exact_jobs": True,
            "original_configuration": True,
            "observer_identity": True,
        },
    }
    store.record_verification(
        conn,
        trial,
        fence_token=token,
        report_json=json.dumps(proof),
        relative_path=f".runtime/m6/test/{trial}/independent.json",
        sha256="b" * 64,
    )


@pytest.mark.parametrize("same_key", [False, True])
def test_simultaneous_creation_is_serialized(dsn, same_key):
    barrier = Barrier(2)
    shared_key = "m6-shared-" + uuid4().hex

    def attempt():
        with connect(dsn) as conn:
            barrier.wait(timeout=5)
            try:
                row, created = store.create_trial(
                    conn,
                    request_key=shared_key if same_key else "m6-unique-" + uuid4().hex,
                    scenario=Scenario.WORKER_FAILURE,
                    source_revision="38b3a46",
                )
                return str(row["id"]), created
            except store.TrialConflict:
                return None, False

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: attempt(), range(2)))
    assert sum(created for _, created in results) == 1
    if same_key:
        assert results[0][0] == results[1][0]
    else:
        assert sum(trial is None for trial, _ in results) == 1
    with connect(dsn) as conn:
        assert conn.execute("SELECT count(*) AS n FROM m6_trials").fetchone()["n"] == 1


def test_rollback_discards_trial_outbox_and_audit_together(dsn):
    with connect(dsn) as conn:
        with pytest.raises(RuntimeError), conn.transaction():
            requested(conn)
            raise RuntimeError("simulated process failure before commit")
        for table in ("m6_trials", "m6_trial_events", "m6_trial_outbox"):
            assert conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"] == 0


def test_committed_request_and_preflight_survive_connection_restart(dsn):
    with connect(dsn) as conn:
        trial = requested(conn)["id"]
    with connect(dsn) as conn:
        assert store.claim_preflight(conn) == trial
    with connect(dsn) as conn:
        assert store.get_trial(conn, trial)["phase"] == "preflight"
        assert store.claim_preflight(conn) is None
        assert (
            conn.execute("SELECT dispatched_at FROM m6_trial_outbox").fetchone()["dispatched_at"]
            is not None
        )


def test_conflicting_idempotency_is_rejected(dsn):
    with connect(dsn) as conn:
        row = requested(conn)
        with pytest.raises(store.TrialConflict):
            store.create_trial(
                conn,
                request_key=row["request_key"],
                scenario=Scenario.WORKER_FAILURE,
                source_revision="abcdef0",
            )


def test_pre_dispatch_crash_allows_only_unused_approval_then_abort(dsn):
    with connect(dsn) as conn:
        trial, _ = armed(conn)
    with connect(dsn) as conn:
        assert store.get_trial(conn, trial)["dispatch_intent_at"] is None
        assert store.request_abort(conn, trial)["phase"] == "aborted"
        assert conn.execute("SELECT * FROM m6_target_leases").fetchone() is None


def test_lost_receipt_and_abort_retain_reservation(dsn):
    with connect(dsn) as conn:
        trial, token, dispatch = sent(conn)
    with connect(dsn) as conn:
        assert store.request_abort(conn, trial)["phase"] == "indeterminate"
    with connect(dsn) as conn:
        with pytest.raises(store.TrialConflict):
            ack(conn, trial, token, dispatch)
        with pytest.raises(store.TrialConflict):
            requested(conn)
        assert conn.execute("SELECT trial_id FROM m6_target_leases").fetchone()["trial_id"] == trial


def test_dispatch_intent_cannot_be_replayed_after_restart(dsn):
    with connect(dsn) as conn:
        trial, token, _ = sent(conn)
    with connect(dsn) as conn:
        with pytest.raises(store.TrialConflict):
            store.begin_dispatch(
                conn,
                trial,
                fence_token=token,
                target_uid="real-test-target",
                target_version="101",
                maximum_seconds=120,
            )
        store.mark_uncertain(conn, trial, fence_token=token, reason="Worker interrupted after send")
        with pytest.raises(store.TrialConflict):
            store.resolve_uncertain(
                conn, trial, fence_token=token, reason="Cleanup not independently observed"
            )


def test_stale_fence_and_dispatch_identity_rejected(dsn):
    with connect(dsn) as conn:
        trial, token, dispatch = sent(conn)
        with pytest.raises(store.TrialConflict):
            ack(conn, trial, uuid4(), dispatch)
        with pytest.raises(store.TrialConflict):
            ack(conn, trial, token, uuid4())
        assert store.get_trial(conn, trial)["phase"] == "armed"


def test_expiry_uses_real_server_time(dsn):
    with connect(dsn) as conn:
        trial, token = armed(conn)
        conn.execute(
            "UPDATE m6_trials SET approval_expires_at=clock_timestamp()+interval '0.1s'"
            " WHERE id=%s",
            (trial,),
        )
        sleep(0.15)
        with pytest.raises(store.TrialConflict):
            store.begin_dispatch(
                conn,
                trial,
                fence_token=token,
                target_uid="test",
                target_version="101",
                maximum_seconds=120,
            )
        assert store.expire_uninjected_approvals(conn) == 1
        assert store.get_trial(conn, trial)["phase"] == "aborted"
        assert store.expire_uninjected_approvals(conn) == 0


def test_dispatched_deadline_retains_target(dsn):
    with connect(dsn) as conn:
        trial, token, _ = sent(conn)
        conn.execute(
            "UPDATE m6_trials SET dispatch_deadline=dispatch_intent_at+interval '0.1s' WHERE id=%s",
            (trial,),
        )
        sleep(0.15)
        assert store.expire_dispatched_trials(conn) == 1
        assert store.get_trial(conn, trial)["phase"] == "indeterminate"
        assert (
            conn.execute("SELECT fence_token FROM m6_target_leases").fetchone()["fence_token"]
            == token
        )


@pytest.mark.parametrize("first", ["abort", "ack"])
def test_abort_and_acknowledgment_compete_without_deadlock(dsn, first):
    with connect(dsn) as conn:
        trial, token, dispatch = sent(conn)
    locked = Event()
    release = Event()

    def operation(name):
        with connect(dsn) as conn:
            if name == first:
                store._locked(conn, trial)
                locked.set()
                assert release.wait(timeout=4)
            else:
                assert locked.wait(timeout=4)
                release.set()
            try:
                return (
                    store.request_abort(conn, trial)
                    if name == "abort"
                    else ack(conn, trial, token, dispatch)
                )["phase"]
            except store.TrialConflict:
                return "rejected"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(operation, ("abort", "ack")))
    with connect(dsn) as conn:
        row = store.get_trial(conn, trial)
        assert row["phase"] in ("indeterminate", "injected")
        assert conn.execute("SELECT * FROM m6_target_leases").fetchone() is not None
        assert row["phase"] != "succeeded"
        if first == "abort":
            assert "rejected" in outcomes
        else:
            assert row["abort_requested"]


def test_success_needs_receipt_independent_cleanup_and_cannot_be_rewritten(dsn):
    with connect(dsn) as conn:
        trial, token, dispatch = sent(conn)
        ack(conn, trial, token, dispatch)
        store.progress(conn, trial, fence_token=token, next_phase=TrialPhase.OBSERVING)
        store.progress(conn, trial, fence_token=token, next_phase=TrialPhase.VERIFYING)
        with pytest.raises(store.TrialConflict):
            store.verified_complete(
                conn, trial, fence_token=token, independently_verified=True, cleanup_verified=True
            )
        independent_receipt(conn, trial, token)
        for kind in ("cleanup",):
            store.attach_artifact(
                conn,
                trial,
                fence_token=token,
                kind=kind,
                relative_path=f".runtime/m6/test/{trial}/{kind}.json",
                sha256="b" * 64,
            )
        row = store.verified_complete(
            conn, trial, fence_token=token, independently_verified=True, cleanup_verified=True
        )
        assert row["phase"] == "succeeded"
        with pytest.raises(psycopg.errors.RaiseException), conn.transaction():
            conn.execute("UPDATE m6_trials SET phase='requested' WHERE id=%s", (trial,))
        with pytest.raises(psycopg.errors.RaiseException), conn.transaction():
            conn.execute("DELETE FROM m6_trial_events WHERE trial_id=%s", (trial,))
        assert conn.execute("SELECT * FROM m6_target_leases").fetchone() is None


def test_indeterminate_reconciliation_keeps_original_outcome(dsn):
    with connect(dsn) as conn:
        trial, token, _ = sent(conn)
        store.mark_uncertain(conn, trial, fence_token=token, reason="Unknown action outcome")
        independent_receipt(conn, trial, token, hypothesis=False)
        for kind in ("cleanup",):
            store.attach_artifact(
                conn,
                trial,
                fence_token=token,
                kind=kind,
                relative_path=f".runtime/m6/test/{trial}/{kind}.json",
                sha256="b" * 64,
            )
        store.resolve_uncertain(
            conn,
            trial,
            fence_token=token,
            reason="Independent checks established restored target and no fault",
        )
        assert store.get_trial(conn, trial)["phase"] == "indeterminate"
        assert conn.execute("SELECT * FROM m6_target_leases").fetchone() is None
        new = requested(conn)
        assert new["id"] != trial


def test_existing_m5_tables_and_records_are_preserved(dsn):
    with connect(dsn) as conn:
        before = conn.execute("SELECT * FROM experiments ORDER BY id").fetchall()
        trial = requested(conn)
        store.request_abort(conn, trial["id"])
        assert conn.execute("SELECT * FROM experiments ORDER BY id").fetchall() == before
        for table in ("incidents", "recoveries", "kubernetes_recoveries", "investigations"):
            assert (
                conn.execute("SELECT to_regclass(%s) AS name", (table,)).fetchone()["name"] == table
            )


def test_different_targets_cannot_arm_conflicting_environment_faults(dsn):
    with connect(dsn) as conn:
        worker = requested(conn)
        store.claim_preflight(conn)
        database, _ = store.create_trial(
            conn,
            request_key="m6-database-" + uuid4().hex,
            scenario=Scenario.DATABASE_CONNECTIVITY,
            source_revision="38b3a46",
        )
        store.claim_preflight(conn)
        store.arm_trial(
            conn,
            worker["id"],
            approved_scope=True,
            cleanup_confirmed=True,
            confirmation="ARM M6 LOCAL TRIAL",
        )
        with pytest.raises(store.TrialConflict):
            store.arm_trial(
                conn,
                database["id"],
                approved_scope=True,
                cleanup_confirmed=True,
                confirmation="ARM M6 LOCAL TRIAL",
            )
        assert store.get_trial(conn, database["id"])["phase"] == "preflight"
        assert conn.execute("SELECT count(*) AS n FROM m6_execution_leases").fetchone()["n"] == 1


def test_trial_intent_cannot_change_after_creation(dsn):
    with connect(dsn) as conn:
        trial = requested(conn)
        with pytest.raises(psycopg.errors.RaiseException), conn.transaction():
            conn.execute(
                "UPDATE m6_trials SET source_revision='abcdef0' WHERE id=%s", (trial["id"],)
            )
        assert store.get_trial(conn, trial["id"])["source_revision"] == "38b3a46"
