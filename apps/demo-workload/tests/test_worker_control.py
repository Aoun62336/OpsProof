"""Bounded worker control and credential separation."""

from unittest.mock import MagicMock
from uuid import UUID

import pytest

from opsproof_demo.worker_control import HOLD_KEY, hold_state, pause_worker, resume_worker


def test_hold_state() -> None:
    redis = MagicMock()
    for ttl, paused in [(42, True), (-2, False), (-1, True), (0, True)]:
        redis.ttl.return_value = ttl
        assert hold_state(redis) == {"paused": paused, "ttl_seconds": max(ttl, 0)}


def test_resume_fixed_key_and_replay() -> None:
    redis = MagicMock()
    for code, result in [(1, "applied"), (2, "replayed"), (0, "not_paused")]:
        redis.eval.return_value = code
        assert resume_worker(redis, UUID(int=9)) == result
        assert redis.eval.call_args.args[2] == HOLD_KEY


def test_pause_does_not_extend_hold() -> None:
    redis = MagicMock()
    redis.set.return_value = True
    assert pause_worker(redis, 420)
    redis.set.assert_called_once_with(HOLD_KEY, "manual-local-fault-drill", ex=420, nx=True)
    redis.set.return_value = None
    assert not pause_worker(redis, 420)


@pytest.mark.parametrize("seconds", [-1, 0, 60, 481, 900, True])
def test_unbounded_hold_rejected(seconds) -> None:
    redis = MagicMock()
    with pytest.raises(ValueError):
        pause_worker(redis, seconds)
    redis.set.assert_not_called()


def test_credentials_are_separate(monkeypatch) -> None:
    from types import SimpleNamespace

    from fastapi.testclient import TestClient

    from opsproof_demo import api

    monkeypatch.setattr(
        api,
        "settings",
        lambda: SimpleNamespace(
            inspection_key="inspect",
            recovery_key="actuate",
        ),
    )
    with TestClient(api.app) as client:
        assert client.get("/api/v1/internal/worker-state").status_code == 401
        assert (
            client.get(
                "/api/v1/internal/worker-state",
                headers={
                    "X-OpsProof-Inspect-Key": "actuate",
                },
            ).status_code
            == 401
        )
        assert (
            client.post(
                "/api/v1/internal/worker/resume",
                headers={
                    "X-OpsProof-Recovery-Key": "inspect",
                },
                json={"recovery_id": str(UUID(int=1))},
            ).status_code
            == 401
        )
