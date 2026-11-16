"""M6 API is disabled by default and does not expose injected success."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from opsproof_control import api, auth, trial_api

KEY = "local-m6-unit-test-key-not-for-deploy"


def test_rejected_without_operator_key(monkeypatch):
    monkeypatch.setattr(auth, "settings", lambda: SimpleNamespace(api_key=KEY))
    with TestClient(api.app) as client:
        assert client.get("/api/v1/m6/trials").status_code == 401
        assert (
            client.post(
                "/api/v1/m6/trials",
                json={"scenario": "worker_failure", "source_revision": "38b3a46"},
                headers={"Idempotency-Key": "test-auth-m6-01"},
            ).status_code
            == 401
        )


def test_disabled_even_with_valid_key(monkeypatch):
    monkeypatch.setattr(auth, "settings", lambda: SimpleNamespace(api_key=KEY))
    monkeypatch.setattr(trial_api, "settings", lambda: SimpleNamespace(m6_enabled=False))
    with TestClient(api.app) as client:
        response = client.get("/api/v1/m6/trials", headers={"X-OpsProof-Key": KEY})
    assert response.status_code == 404


def test_arm_has_separate_disable_switch(monkeypatch):
    monkeypatch.setattr(auth, "settings", lambda: SimpleNamespace(api_key=KEY))
    monkeypatch.setattr(
        trial_api, "settings", lambda: SimpleNamespace(m6_enabled=True, m6_arm_enabled=False)
    )
    with TestClient(api.app) as client:
        response = client.post(
            "/api/v1/m6/trials/00000000-0000-0000-0000-000000000001/arm",
            headers={"X-OpsProof-Key": KEY},
            json={
                "confirmation": "ARM M6 LOCAL TRIAL",
                "approved_test_scope": True,
                "cleanup_plan_confirmed": True,
            },
        )
    assert response.status_code == 403


def test_no_http_endpoint_can_self_attest_verification():
    paths = {route.path for route in trial_api.router.routes}
    assert not any(path.endswith(("/succeed", "/inject", "/complete")) for path in paths)


def test_arm_requires_json_booleans():
    """Avoid implicit string -> boolean coercion for an explicit approval field."""
    import pytest
    from pydantic import ValidationError

    from opsproof_control.trial_api import ArmInput

    with pytest.raises(ValidationError):
        ArmInput.model_validate(
            {
                "confirmation": "ARM M6 LOCAL TRIAL",
                "approved_test_scope": "yes",
                "cleanup_plan_confirmed": True,
            }
        )
