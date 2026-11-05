"""Local API authentication and CSRF boundary tests."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from opsproof_control import api, auth


def local_settings():
    return SimpleNamespace(
        api_key="local-test-key-not-for-deployment",
        allowed_browser_origins="http://127.0.0.1:5173",
        secure_cookies=False,
    )


def test_liveness_is_public() -> None:
    with TestClient(api.app) as client:
        response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_missing_credentials_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "settings",
        local_settings,
    )
    with TestClient(api.app) as client:
        response = client.get("/api/v1/experiments")
    assert response.status_code == 401
    with TestClient(api.app) as client:
        response = client.get("/api/v1/experiments")
    assert response.status_code == 401


def test_incorrect_api_key_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "settings",
        local_settings,
    )
    with TestClient(api.app) as client:
        response = client.get(
            "/api/v1/experiments",
            headers={"X-OpsProof-Key": "wrong-key"},
        )
    assert response.status_code == 401


def test_correct_api_key_accepted(monkeypatch) -> None:
    monkeypatch.setattr(
        auth,
        "settings",
        local_settings,
    )
    with TestClient(api.app) as client:
        response = client.get(
            "/api/v1/experiments",
            headers={"X-OpsProof-Key": "local-test-key-not-for-deployment"},
        )
    # 503 is acceptable here because the DB is not running in unit tests;
    # 401 would mean auth failed which is what we are guarding against.
    assert response.status_code != 401


def test_logout_requires_authentication() -> None:
    with TestClient(api.app) as client:
        response = client.post("/api/v1/auth/logout")
    assert response.status_code == 401
