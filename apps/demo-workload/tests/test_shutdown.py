"""Termination signals must request a cooperative, successful shutdown."""

import signal

import pytest

from opsproof_demo.shutdown import ShutdownRequested, checkpoint, lifecycle, stopping


@pytest.fixture(autouse=True)
def reset_shutdown(monkeypatch):
    monkeypatch.setenv("OPSPROOF_DATABASE_URL", "postgresql://unused/unused")
    monkeypatch.setenv("OPSPROOF_REDIS_URL", "redis://unused:6379/0")
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


def test_worker_finishes_current_entry_and_does_not_start_next(monkeypatch):
    from unittest.mock import MagicMock

    from opsproof_demo import worker

    redis = MagicMock()
    redis.get.return_value = None
    redis.xautoclaim.return_value = ["0-0", [("1-0", {}), ("2-0", {})]]
    monkeypatch.setattr(worker.Redis, "from_url", lambda *args, **kwargs: redis)
    process = MagicMock(side_effect=lambda *args: stopping.set())
    monkeypatch.setattr(worker, "process_entry", process)
    with lifecycle():
        worker.run()
    process.assert_called_once_with(redis, "1-0", {})
    redis.close.assert_called_once()


def test_hold_wait_is_interruptible_without_processing_or_acknowledging(monkeypatch):
    from unittest.mock import MagicMock

    from opsproof_demo import worker

    redis = MagicMock()
    # No hold before claim; hold appears while the delivered entry waits.
    redis.get.side_effect = [None, "held"]
    redis.xautoclaim.return_value = ["0-0", [("1-0", {})]]
    monkeypatch.setattr(worker.Redis, "from_url", lambda *args, **kwargs: redis)
    monkeypatch.setattr(stopping, "wait", lambda timeout: stopping.set())
    process = MagicMock()
    monkeypatch.setattr(worker, "process_entry", process)
    with lifecycle():
        worker.run()
    process.assert_not_called()
    redis.xack.assert_not_called()
    redis.close.assert_called_once()
