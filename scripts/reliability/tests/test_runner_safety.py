from types import SimpleNamespace

import pytest

from scripts.reliability.run_k6_local import execute


def args(tmp_path, **overrides):
    data = dict(
        acknowledge="M6_LOCAL_DURABLE_JOBS",
        run_id="m6-trial-20261108",
        rate=2,
        seconds=30,
        duration_ms=250,
        vus=4,
        timeout=300,
        kubeconfig=tmp_path / "kubeconfig",
        output_root=tmp_path / "output",
    )
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.mark.parametrize(
    "changes",
    [
        {"acknowledge": ""},
        {"run_id": "real-production"},
        {"rate": 50},
        {"seconds": 121},
        {"rate": 5, "seconds": 120},
        {"duration_ms": 3000},
    ],
)
def test_invalid_or_unbounded_load_never_calls_kubectl(tmp_path, monkeypatch, changes):
    def forbidden(*args, **kwargs):
        raise AssertionError("No subprocess or cluster access on invalid request")

    monkeypatch.setattr("scripts.reliability.run_k6_local.local_prefix", forbidden)
    with pytest.raises(ValueError):
        execute(args(tmp_path, **changes))


def test_low_host_memory_blocks_load_before_any_port_or_job_write(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.reliability.run_k6_local.local_prefix", lambda _: ["kubectl"])
    monkeypatch.setattr("scripts.reliability.run_k6_local.memory_available", lambda: 1024**3)

    def forbidden():
        raise AssertionError("No port-forward or job write allowed")

    monkeypatch.setattr("scripts.reliability.run_k6_local.assert_port_free", forbidden)
    with pytest.raises(RuntimeError, match="Host RAM"):
        execute(args(tmp_path))
