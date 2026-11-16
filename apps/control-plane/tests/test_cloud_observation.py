"""Cloud observation remains usable while every local mutation capability is off."""

from contextlib import contextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from opsproof_control import api, auth, kubernetes_operations, kubernetes_worker, operations
from opsproof_control.config import Settings


def config(**overrides):
    return Settings(
        database_url="postgresql://localhost:5999/unavailable",
        redis_url="redis://localhost:6399",
        api_key="unit-cloud-key",
        environment="temporary-eks",
        kubernetes_observation_enabled=True,
        **overrides,
    )


@pytest.mark.parametrize(
    "flag", ["recovery_enabled", "kubernetes_recovery_enabled", "m6_arm_enabled"]
)
def test_cloud_configuration_cannot_enable_local_actuators(flag):
    with pytest.raises(ValidationError, match="Temporary EKS"):
        config(**{flag: True})


def test_observation_and_history_are_authenticated_and_read_only(monkeypatch):
    settings = config()

    @contextmanager
    def connection():
        yield SimpleNamespace(execute=lambda *_: SimpleNamespace(fetchall=lambda: []))

    monkeypatch.setattr(auth, "settings", lambda: settings)
    monkeypatch.setattr(kubernetes_operations, "settings", lambda: settings)
    monkeypatch.setattr(operations, "settings", lambda: settings)
    monkeypatch.setattr(
        kubernetes_operations, "pool", lambda: SimpleNamespace(connection=connection)
    )
    with TestClient(api.app) as client:
        assert client.get("/api/v1/kubernetes/workloads").status_code == 401
        headers = {"X-OpsProof-Key": "unit-cloud-key", "Idempotency-Key": "cloud-observation-only"}
        response = client.get("/api/v1/kubernetes/workloads", headers=headers)
        assert response.status_code == 200
        assert response.json()["enabled"] is True
        assert response.json()["environment"] == "temporary-eks"
        assert response.json()["recovery_enabled"] is False
        assert client.get("/api/v1/kubernetes/recoveries", headers=headers).status_code == 200
        capabilities = client.get("/api/v1/capabilities", headers=headers).json()
        assert capabilities["environment_label"] == "Temporary EKS"
        assert capabilities["kubernetes_observation_enabled"] is True
        assert capabilities["kubernetes_recovery_enabled"] is False
        response = client.post(
            "/api/v1/kubernetes/recoveries",
            headers=headers,
            json={
                "action": "restore_demo_worker",
                "incident_fingerprint": "a" * 16,
                "run_id": str(uuid4()),
            },
        )
        assert response.status_code == 403


def test_read_only_observer_never_processes_or_mutates_recoveries(monkeypatch):
    statements, calls = [], []

    @contextmanager
    def connection():
        def execute(statement, *_):
            statements.append(statement)
            return SimpleNamespace(fetchall=lambda: [])

        yield SimpleNamespace(execute=execute)

    def target(method="GET", *_args, **_kwargs):
        calls.append(method)
        return {
            "kind": "Deployment",
            "metadata": {
                "name": "demo-worker",
                "namespace": "opsproof-demo",
                "uid": "owned-worker",
                "resourceVersion": "1",
                "generation": 1,
            },
            "spec": {
                "replicas": 1,
                "template": {
                    "spec": {
                        "containers": [
                            {"image": "verified-image", "resources": {"requests": {}, "limits": {}}}
                        ]
                    }
                },
            },
            "status": {"readyReplicas": 1},
        }

    monkeypatch.setattr(kubernetes_worker, "settings", config)
    monkeypatch.setattr(kubernetes_worker, "pool", lambda: SimpleNamespace(connection=connection))
    monkeypatch.setattr(kubernetes_worker.kubernetes_client, "request", target)
    monkeypatch.setattr(
        kubernetes_worker,
        "telemetry",
        lambda: {
            "ready": True,
            "queued": 0,
            "sample_time": datetime.now(UTC).timestamp(),
        },
    )
    kubernetes_worker.execute_next()
    kubernetes_worker.observe_and_verify()
    assert calls == ["GET"]
    assert any("INSERT INTO kubernetes_observations" in statement for statement in statements)
    assert not any("kubernetes_recoveries" in statement for statement in statements)
