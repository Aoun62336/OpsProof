"""Actual process loss and immutable independent receipt checks on disposable SQL."""

import json
import os
import subprocess
import sys
import time
from uuid import uuid4

import psycopg
import pytest
from test_postgres_safety import ack, armed, connect, independent_receipt, sent
from test_postgres_safety import dsn as dsn

from opsproof_control import trial_store as store
from opsproof_control.trial_state import TrialPhase


@pytest.mark.parametrize("boundary", ["intent", "acknowledgment"])
def test_real_executor_process_kill_never_replays_or_releases(dsn, tmp_path, boundary):
    with connect(dsn) as conn:
        trial, token = armed(conn)
    marker = tmp_path / "committed.json"
    script = """
import json, os, time
from pathlib import Path
from uuid import UUID
import psycopg
from psycopg.rows import dict_row
from opsproof_control import trial_store as store
trial, token = UUID(os.environ['M6_TEST_TRIAL']), UUID(os.environ['M6_TEST_FENCE'])
with psycopg.connect(os.environ['OPSPROOF_M6_TEST_DATABASE_URL'], row_factory=dict_row) as conn:
    dispatch = store.begin_dispatch(
        conn,trial,fence_token=token,target_uid='process-target',
        target_version='101',maximum_seconds=120)
if os.environ['M6_TEST_BOUNDARY'] == 'acknowledgment':
    with psycopg.connect(os.environ['OPSPROOF_M6_TEST_DATABASE_URL'], row_factory=dict_row) as conn:
        store.acknowledge_injection(conn,trial,fence_token=token,dispatch_id=dispatch,receipt_path='.runtime/m6/process/receipt.json',receipt_sha256='a'*64)
Path(os.environ['M6_TEST_MARKER']).write_text(json.dumps({'dispatch':str(dispatch)}))
time.sleep(30)
"""
    env = {
        **os.environ,
        "M6_TEST_TRIAL": str(trial),
        "M6_TEST_FENCE": str(token),
        "M6_TEST_BOUNDARY": boundary,
        "M6_TEST_MARKER": str(marker),
    }
    child = subprocess.Popen(
        [sys.executable, "-c", script],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(0.05)
        assert marker.exists(), "Child did not reach committed crash boundary"
        child.terminate()
        child.wait(timeout=5)
        assert child.returncode != 0
        with connect(dsn) as conn:
            row = store.get_trial(conn, trial)
            assert str(row["dispatch_id"]) == json.loads(marker.read_text())["dispatch"]
            with pytest.raises(store.TrialConflict):
                store.begin_dispatch(
                    conn,
                    trial,
                    fence_token=token,
                    target_uid="process-target",
                    target_version="101",
                    maximum_seconds=120,
                )
            store.mark_uncertain(
                conn,
                trial,
                fence_token=token,
                reason="Actual executor process killed after committed boundary",
            )
            assert store.get_trial(conn, trial)["phase"] == "indeterminate"
            assert (
                conn.execute("SELECT trial_id FROM m6_execution_leases").fetchone()["trial_id"]
                == trial
            )
            assert (
                conn.execute("SELECT trial_id FROM m6_target_leases").fetchone()["trial_id"]
                == trial
            )
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)


def test_flags_and_three_artifact_classes_are_insufficient(dsn):
    with connect(dsn) as conn:
        trial, token, dispatch = sent(conn)
        ack(conn, trial, token, dispatch)
        store.progress(conn, trial, fence_token=token, next_phase=TrialPhase.OBSERVING)
        store.progress(conn, trial, fence_token=token, next_phase=TrialPhase.VERIFYING)
        for kind in ("independent", "cleanup"):
            store.attach_artifact(
                conn,
                trial,
                fence_token=token,
                kind=kind,
                relative_path=f".runtime/m6/claims/{kind}.json",
                sha256="b" * 64,
            )
        with pytest.raises(store.TrialConflict, match="dispatch-bound"):
            store.verified_complete(
                conn, trial, fence_token=token, independently_verified=True, cleanup_verified=True
            )


def test_negative_independent_hypothesis_cannot_become_success(dsn):
    with connect(dsn) as conn:
        trial, token, dispatch = sent(conn)
        ack(conn, trial, token, dispatch)
        store.progress(conn, trial, fence_token=token, next_phase=TrialPhase.OBSERVING)
        store.progress(conn, trial, fence_token=token, next_phase=TrialPhase.VERIFYING)
        independent_receipt(conn, trial, token, hypothesis=False)
        with pytest.raises(store.TrialConflict, match="hypothesis"):
            store.verified_complete(
                conn, trial, fence_token=token, independently_verified=True, cleanup_verified=True
            )


def test_verification_artifact_and_dispatch_identity_are_immutable(dsn):
    with connect(dsn) as conn:
        trial, token, _ = sent(conn)
        independent_receipt(conn, trial, token)
        for statement, parameters in (
            (
                "UPDATE m6_trial_verifications SET hypothesis_verified=false WHERE trial_id=%s",
                (trial,),
            ),
            ("DELETE FROM m6_trial_verifications WHERE trial_id=%s", (trial,)),
            ("UPDATE m6_trial_artifacts SET sha256=%s WHERE trial_id=%s", ("d" * 64, trial)),
            ("UPDATE m6_trials SET target_uid='another-target' WHERE id=%s", (trial,)),
            ("UPDATE m6_trials SET dispatch_id=%s WHERE id=%s", (uuid4(), trial)),
        ):
            with pytest.raises(psycopg.errors.RaiseException), conn.transaction():
                conn.execute(statement, parameters)
