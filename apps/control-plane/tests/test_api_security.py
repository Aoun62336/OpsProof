"""Local API authentication behavior."""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from opsproof_control import api

client = TestClient(api.app)


def test_liveness_is_public() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "alive"}


def test_missing_api_key_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "settings",
        lambda: SimpleNamespace(api_key="test-secret-that-is-not-used-in-production"),
    )

    response = client.get("/api/v1/experiments/00000000-0000-0000-0000-000000000001")

    assert response.status_code == 401


def test_incorrect_api_key_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "settings",
        lambda: SimpleNamespace(api_key="test-secret-that-is-not-used-in-production"),
    )

    response = client.get(
        "/api/v1/experiments/00000000-0000-0000-0000-000000000001",
        headers={
            "X-OpsProof-Key": "incorrect-secret",
        },
    )

    assert response.status_code == 401
