"""Termination signals must request a cooperative, successful shutdown."""

import signal

import pytest

from opsproof_control.shutdown import ShutdownRequested, checkpoint, lifecycle, stopping


@pytest.fixture(autouse=True)
def reset_shutdown():
    stopping.clear()
    yield
    stopping.clear()


@pytest.mark.parametrize("signum", [signal.SIGTERM, signal.SIGINT])
def test_signal_sets_flag_without_interrupting_current_operation(signum):
    previous = signal.getsignal(signum)
    with lifecycle():
        signal.raise_signal(signum)
        assert stopping.is_set()
        # Current work can commit before choosing a safe checkpoint.
        with pytest.raises(ShutdownRequested):
            checkpoint()
    assert signal.getsignal(signum) == previous


def test_lifecycle_suppresses_cooperative_stop_but_not_business_errors():
    with lifecycle():
        stopping.set()
        checkpoint()
    with pytest.raises(ValueError), lifecycle():
        raise ValueError("real error")


def test_interrupted_handler_is_not_acknowledged_or_followed_by_tick(monkeypatch):
    from unittest.mock import MagicMock
    from uuid import uuid4

    from opsproof_control import streams

    redis = MagicMock()
    tick = MagicMock()
    monkeypatch.setattr(streams, "redis_client", lambda: redis)
    monkeypatch.setattr(streams, "messages", lambda *args: [("1-0", {"run_id": str(uuid4())})])

    def handler(run_id):
        stopping.set()
        checkpoint()

    with lifecycle():
        streams.consume("stream", "group", handler, tick)
    redis.xack.assert_not_called()
    tick.assert_not_called()


def test_completed_handler_is_acknowledged_but_next_message_is_left_pending(monkeypatch):
    from unittest.mock import MagicMock
    from uuid import uuid4

    from opsproof_control import streams

    redis = MagicMock()
    tick = MagicMock()
    entries = [("1-0", {"run_id": str(uuid4())}), ("2-0", {"run_id": str(uuid4())})]
    monkeypatch.setattr(streams, "redis_client", lambda: redis)
    monkeypatch.setattr(streams, "messages", lambda *args: entries)
    handler = MagicMock(side_effect=lambda run_id: stopping.set())
    with lifecycle():
        streams.consume("stream", "group", handler, tick)
    handler.assert_called_once()
    redis.xack.assert_called_once_with("stream", "group", "1-0")
    tick.assert_not_called()


def test_evidence_shutdown_does_not_fail_experiment(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from uuid import uuid4

    from opsproof_control import evidence

    monkeypatch.setattr(evidence, "settings", lambda: SimpleNamespace(target_url="http://unused"))
    conn = MagicMock()
    conn.execute.return_value.fetchone.side_effect = [
        {"status": "verifying", "count": 1},
        {"details": {"job_ids": [str(uuid4())]}},
    ]
    db = MagicMock()
    db.connection.return_value.__enter__.return_value = conn
    monkeypatch.setattr(evidence, "pool", lambda: db)
    fail = MagicMock()
    monkeypatch.setattr(evidence, "fail", fail)
    stopping.set()
    with pytest.raises(ShutdownRequested):
        evidence.verify(uuid4())
    fail.assert_not_called()


def test_action_stop_preserves_running_record_for_idempotent_retry(monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from uuid import uuid4

    from opsproof_control import action

    conn = MagicMock()
    conn.execute.return_value.fetchone.return_value = {
        "status": "running",
        "scenario": "queue-burst",
        "count": 5,
        "duration_ms": 250,
    }
    db = MagicMock()
    db.connection.return_value.__enter__.return_value = conn
    monkeypatch.setattr(action, "pool", lambda: db)
    monkeypatch.setattr(action, "settings", lambda: SimpleNamespace(target_url="http://unused"))
    http = MagicMock()
    http.get.side_effect = lambda *args: stopping.set() or MagicMock()
    factory = MagicMock()
    factory.return_value.__enter__.return_value = http
    monkeypatch.setattr(action.httpx, "Client", factory)
    fail, enqueue = MagicMock(), MagicMock()
    monkeypatch.setattr(action, "fail", fail)
    monkeypatch.setattr(action, "enqueue", enqueue)
    with pytest.raises(ShutdownRequested):
        action.execute(uuid4())
    http.post.assert_not_called()
    fail.assert_not_called()
    enqueue.assert_not_called()


def test_evidence_joins_review_thread_before_returning(monkeypatch):
    from threading import Event
    from threading import enumerate as threads
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from opsproof_control import evidence, investigation_worker, recovery_worker

    started, finished = Event(), Event()

    def investigate():
        started.set()
        assert stopping.wait(3)
        finished.set()

    def consume(*args):
        assert started.wait(3)
        stopping.set()

    verify = MagicMock()
    monkeypatch.setattr(evidence, "settings", lambda: SimpleNamespace(evidence_stream="stream"))
    monkeypatch.setattr(evidence, "consume", consume)
    monkeypatch.setattr(investigation_worker, "process_next_investigation", investigate)
    monkeypatch.setattr(recovery_worker, "verify_next_recovery", verify)
    evidence.run()
    assert finished.is_set()
    assert not any(t.name == "evidence-review" for t in threads())
    verify.assert_not_called()
