from types import SimpleNamespace

from fastapi.testclient import TestClient

from opsproof_control import api, auth, workload_reuse


def test_reuse_is_disabled_before_any_workload_request(monkeypatch):
    monkeypatch.setattr(auth, "settings", lambda: SimpleNamespace(api_key="test-only-key"))
    monkeypatch.setattr(
        workload_reuse, "settings", lambda: SimpleNamespace(m6_enabled=True, m6_reuse_enabled=False)
    )

    def unexpected():
        raise AssertionError("Disabled reuse must not call the workload")

    monkeypatch.setattr(workload_reuse, "collect", unexpected)
    with TestClient(api.app) as client:
        assert client.get("/api/v1/m6/reuse/investigations").status_code == 401
        assert (
            client.post(
                "/api/v1/m6/reuse/investigations", headers={"X-OpsProof-Key": "test-only-key"}
            ).status_code
            == 404
        )


def test_second_workload_has_no_recovery_target_parameter(monkeypatch):
    monkeypatch.setattr(auth, "settings", lambda: SimpleNamespace(api_key="test-only-key"))
    with TestClient(api.app) as client:
        response = client.post(
            "/api/v1/kubernetes/recoveries",
            headers={"X-OpsProof-Key": "test-only-key", "Idempotency-Key": "reuse-denial-0001"},
            json={
                "action": "restore_demo_worker",
                "target": "opsproof-reuse-test",
                "incident_fingerprint": "0" * 16,
                "run_id": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert response.status_code == 422
