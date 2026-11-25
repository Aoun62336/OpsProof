"""Actual concurrent and reordered alert deliveries against owned disposable SQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Event
from uuid import uuid4

import pytest
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from test_postgres_safety import connect, dsn  # noqa: F401 - guarded SQL fixture

from opsproof_control import incidents, investigation_worker
from opsproof_control.benchmark import CASES, make_snapshot


@pytest.fixture
def database(request, monkeypatch):
    url = request.getfixturevalue("dsn")

    class Pool:
        def connection(self):
            return connect(url)

    monkeypatch.setattr(incidents, "pool", Pool)
    # A real pool keeps sessions alive after each call: the test must detect a
    # leaked advisory lock rather than accidentally releasing it by closing SQL.
    with ConnectionPool(
        url,
        min_size=1,
        max_size=3,
        timeout=5,
        kwargs={"row_factory": dict_row, "connect_timeout": 3},
    ) as worker_pool:
        monkeypatch.setattr(investigation_worker, "pool", lambda: worker_pool)
        yield url


def deliver(fingerprint, started, status="firing", ended=None):
    alert = incidents.IncomingAlert(
        fingerprint=fingerprint, status=status, startsAt=started, endsAt=ended
    )
    return incidents.ingest_alertmanager_webhook(incidents.AlertmanagerWebhook(alerts=[alert]))


def read_incident(url, fingerprint):
    with connect(url) as conn:
        row = conn.execute(
            "SELECT * FROM incidents WHERE fingerprint=%s", (fingerprint,)
        ).fetchone()
        events = conn.execute(
            "SELECT status FROM incident_events WHERE incident_fingerprint=%s ORDER BY id",
            (fingerprint,),
        ).fetchall()
    return row, [item["status"] for item in events]


def test_simultaneous_first_delivery_creates_one_incident_and_event(database):
    fingerprint = uuid4().hex
    started = datetime.now(UTC)
    barrier = Barrier(2)

    def submit():
        barrier.wait(timeout=5)
        return deliver(fingerprint, started)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(submit) for _ in range(2)]
        assert all(f.result(timeout=10)["processed"] == 1 for f in futures)
    row, events = read_incident(database, fingerprint)
    assert row["status"] == "firing"
    assert events == ["firing"]


def test_late_resolution_and_firing_cannot_overwrite_new_occurrence(database):
    fingerprint = uuid4().hex
    first = datetime.now(UTC) - timedelta(minutes=3)
    second = first + timedelta(minutes=2)
    deliver(fingerprint, first)
    deliver(fingerprint, first, "resolved", first + timedelta(seconds=30))
    deliver(fingerprint, second)
    deliver(fingerprint, first, "resolved", first + timedelta(seconds=30))
    deliver(fingerprint, first)
    row, events = read_incident(database, fingerprint)
    assert row["status"] == "firing" and row["started_at"] == second
    assert row["resolved_at"] is None
    assert events == ["firing", "resolved", "firing"]
    with connect(database) as conn:
        times = conn.execute(
            "SELECT occurred_at,created_at FROM incident_events "
            "WHERE incident_fingerprint=%s ORDER BY id",
            (fingerprint,),
        ).fetchall()
    assert [item["occurred_at"] for item in times] == [first, first + timedelta(seconds=30), second]
    assert all(item["created_at"] >= item["occurred_at"] for item in times)


def test_resolved_occurrence_is_not_reopened_by_repeated_firing(database):
    fingerprint = uuid4().hex
    started = datetime.now(UTC) - timedelta(minutes=1)
    ended = started + timedelta(seconds=30)
    deliver(fingerprint, started)
    deliver(fingerprint, started, "resolved", ended)
    deliver(fingerprint, started)
    row, events = read_incident(database, fingerprint)
    assert row["status"] == "resolved" and row["resolved_at"] == ended
    assert events == ["firing", "resolved"]


def test_repeated_status_with_new_start_preserves_new_occurrence(database):
    fingerprint = uuid4().hex
    started = datetime.now(UTC) - timedelta(minutes=2)
    deliver(fingerprint, started)
    deliver(fingerprint, started + timedelta(minutes=1))
    deliver(fingerprint, started, "resolved", started + timedelta(seconds=20))
    row, events = read_incident(database, fingerprint)
    assert row["status"] == "firing"
    assert row["started_at"] == started + timedelta(minutes=1)
    assert events == ["firing", "firing"]


def test_invalid_resolution_time_does_not_change_state(database):
    fingerprint = uuid4().hex
    started = datetime.now(UTC)
    deliver(fingerprint, started)
    deliver(fingerprint, started, "resolved", started - timedelta(seconds=1))
    row, events = read_incident(database, fingerprint)
    assert row["status"] == "firing" and events == ["firing"]


def queued_ai(url):
    identifier = uuid4()
    fingerprint = uuid4().hex
    snapshot = make_snapshot(CASES[0])
    from psycopg.types.json import Jsonb

    with connect(url) as conn:
        conn.execute(
            "INSERT INTO incidents(fingerprint,name,target,severity,status,"
            "started_at,last_seen_at) "
            "VALUES (%s,'fixture','fixture','warning','firing',now(),now())",
            (fingerprint,),
        )
        conn.execute(
            "INSERT INTO investigations(id,request_key,incident_fingerprint,status,"
            "snapshot,ai_status,ai_requested_at) "
            "VALUES (%s,%s,%s,'ready',%s,'queued',now())",
            (identifier, uuid4().hex, fingerprint, Jsonb(snapshot.model_dump(mode="json"))),
        )
    return identifier


def test_live_ai_owner_cannot_be_reaped_or_dispatched_twice(database, monkeypatch):
    from opsproof_control import model_provider

    identifier = queued_ai(database)
    entered, release = Event(), Event()
    calls = []

    def compare(snapshot):
        calls.append(snapshot)
        with connect(database) as conn:
            assert (
                conn.execute(
                    "SELECT ai_status FROM investigations WHERE id=%s", (identifier,)
                ).fetchone()["ai_status"]
                == "running"
            )
        entered.set()
        assert release.wait(timeout=10)
        return {
            "diagnosis": {},
            "provider": "intercepted",
            "model": "fixture",
            "usage": {},
            "elapsed_ms": 1,
        }

    monkeypatch.setattr(model_provider, "compare", compare)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(investigation_worker.process_next_ai)
        try:
            assert entered.wait(timeout=5)
            with connect(database) as conn:
                conn.execute(
                    "UPDATE investigations SET ai_started_at=now()-interval '10 minutes' "
                    "WHERE id=%s",
                    (identifier,),
                )
            investigation_worker.process_next_ai()
            with connect(database) as conn:
                assert (
                    conn.execute(
                        "SELECT ai_status FROM investigations WHERE id=%s", (identifier,)
                    ).fetchone()["ai_status"]
                    == "running"
                )
        finally:
            release.set()
        future.result(timeout=10)
    assert len(calls) == 1
    with connect(database) as conn:
        assert (
            conn.execute(
                "SELECT ai_status FROM investigations WHERE id=%s", (identifier,)
            ).fetchone()["ai_status"]
            == "ready"
        )
        assert conn.execute(
            "SELECT pg_try_advisory_lock(%s) AS acquired", (investigation_worker.AI_WORKER_LOCK,)
        ).fetchone()["acquired"]
        conn.execute("SELECT pg_advisory_unlock(%s)", (investigation_worker.AI_WORKER_LOCK,))


def test_abandoned_ai_is_failed_once_without_retry(database, monkeypatch):
    from opsproof_control import model_provider

    identifier = queued_ai(database)
    with connect(database) as conn:
        conn.execute(
            "UPDATE investigations SET ai_status='running',"
            "ai_started_at=now()-interval '10 minutes' WHERE id=%s",
            (identifier,),
        )

    def forbidden(_):
        pytest.fail("Unknown external work must never be retried")

    monkeypatch.setattr(model_provider, "compare", forbidden)
    investigation_worker.process_next_ai()
    investigation_worker.process_next_ai()
    with connect(database) as conn:
        row = conn.execute(
            "SELECT ai_status,error FROM investigations WHERE id=%s", (identifier,)
        ).fetchone()
    assert row["ai_status"] == "failed" and "unknown" in row["error"]


def test_recent_unowned_ai_is_not_prematurely_failed(database, monkeypatch):
    from opsproof_control import model_provider

    identifier = queued_ai(database)
    with connect(database) as conn:
        conn.execute(
            "UPDATE investigations SET ai_status='running',"
            "ai_started_at=now()-interval '100 seconds' WHERE id=%s",
            (identifier,),
        )

    def forbidden(_):
        pytest.fail("Already dispatched work must not be repeated")

    monkeypatch.setattr(model_provider, "compare", forbidden)
    investigation_worker.process_next_ai()
    with connect(database) as conn:
        row = conn.execute(
            "SELECT ai_status FROM investigations WHERE id=%s", (identifier,)
        ).fetchone()
        assert row["ai_status"] == "running"
        # End the owned fixture explicitly so later tests have no pending state.
        conn.execute("UPDATE investigations SET ai_status='failed' WHERE id=%s", (identifier,))


def test_opposite_batch_order_is_serialized_without_duplicate_events(database):
    fingerprints = [uuid4().hex, uuid4().hex]
    started = datetime.now(UTC)
    barrier = Barrier(2)

    def submit(reverse):
        alerts = [
            incidents.IncomingAlert(fingerprint=value, status="firing", startsAt=started)
            for value in fingerprints
        ]
        barrier.wait(timeout=5)
        incidents.ingest_alertmanager_webhook(
            incidents.AlertmanagerWebhook(alerts=list(reversed(alerts)) if reverse else alerts)
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(submit, reverse) for reverse in (False, True)]
        for future in futures:
            future.result(timeout=10)
    for fingerprint in fingerprints:
        assert read_incident(database, fingerprint)[1] == ["firing"]


def test_provider_failure_releases_pooled_ownership_without_retry(database, monkeypatch):
    from opsproof_control import model_provider

    identifier = queued_ai(database)
    calls = []

    def rejected(_):
        calls.append(True)
        raise ValueError("private provider response fixture")

    monkeypatch.setattr(model_provider, "compare", rejected)
    investigation_worker.process_next_ai()
    investigation_worker.process_next_ai()
    assert len(calls) == 1
    with connect(database) as conn:
        row = conn.execute(
            "SELECT ai_status,error FROM investigations WHERE id=%s", (identifier,)
        ).fetchone()
        assert row == {"ai_status": "failed", "error": "AI evaluation failed: ValueError"}
        assert conn.execute(
            "SELECT pg_try_advisory_lock(%s) AS owned", (investigation_worker.AI_WORKER_LOCK,)
        ).fetchone()["owned"]
        conn.execute("SELECT pg_advisory_unlock(%s)", (investigation_worker.AI_WORKER_LOCK,))
