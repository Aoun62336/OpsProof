"""Incident-ingestion contract and deduplication tests."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from opsproof_control import api, incidents


def sample_alert() -> incidents.IncomingAlert:
    return incidents.IncomingAlert(
        status="firing",
        fingerprint="a" * 16,
        labels={
            "alertname": "OpsProofDemoAPIUnavailable",
            "job": "opsproof-demo-api",
            "severity": "critical",
        },
        annotations={
            "summary": "Demo API unavailable",
        },
        startsAt=datetime(2026, 11, 24, tzinfo=UTC),
    )


def test_invalid_webhook_token_rejected(monkeypatch) -> None:
    monkeypatch.setattr(
        incidents,
        "settings",
        lambda: SimpleNamespace(alert_webhook_token="local-test-token"),
    )

    with TestClient(api.app) as client:
        # Missing token
        resp = client.post(
            "/api/v1/internal/alertmanager",
            json={"alerts": [sample_alert().model_dump(mode="json")]},
        )
        assert resp.status_code == 401

        # Wrong token
        resp = client.post(
            "/api/v1/internal/alertmanager",
            headers={"Authorization": "Bearer wrong-token"},
            json={"alerts": [sample_alert().model_dump(mode="json")]},
        )
        assert resp.status_code == 401


def test_valid_alert_ingested(monkeypatch) -> None:
    monkeypatch.setattr(
        incidents,
        "settings",
        lambda: SimpleNamespace(alert_webhook_token="local-test-token"),
    )

    mock_conn = MagicMock()
    # First query checks if incident exists -> None (new incident)
    mock_conn.execute.return_value.fetchone.return_value = None

    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_conn)
    cm.__exit__ = MagicMock(return_value=False)

    mock_pool = MagicMock()
    mock_pool.connection.return_value = cm
    monkeypatch.setattr(incidents, "pool", lambda: mock_pool)

    with TestClient(api.app) as client:
        resp = client.post(
            "/api/v1/internal/alertmanager",
            headers={"Authorization": "Bearer local-test-token"},
            json={"alerts": [sample_alert().model_dump(mode="json")]},
        )
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "processed": 1}

    # Verify both incident and incident_events were inserted
    calls = [str(call) for call in mock_conn.execute.mock_calls]
    assert any("INSERT INTO incidents" in c for c in calls)
    assert any("INSERT INTO incident_events" in c for c in calls)


def test_duplicate_firing_alert_does_not_duplicate_event(monkeypatch) -> None:
    monkeypatch.setattr(
        incidents,
        "settings",
        lambda: SimpleNamespace(alert_webhook_token="local-test-token"),
    )

    mock_conn = MagicMock()
    # Incident already exists with status "firing"
    mock_conn.execute.return_value.fetchone.return_value = {
        "status": "firing",
        "started_at": sample_alert().startsAt,
        "resolved_at": None,
    }

    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_conn)
    cm.__exit__ = MagicMock(return_value=False)

    mock_pool = MagicMock()
    mock_pool.connection.return_value = cm
    monkeypatch.setattr(incidents, "pool", lambda: mock_pool)

    with TestClient(api.app) as client:
        resp = client.post(
            "/api/v1/internal/alertmanager",
            headers={"Authorization": "Bearer local-test-token"},
            json={"alerts": [sample_alert().model_dump(mode="json")]},
        )
        assert resp.status_code == 200

    calls = [str(call) for call in mock_conn.execute.mock_calls]
    # UPDATE incidents was called, but NO INSERT INTO incident_events
    assert any("UPDATE incidents" in c for c in calls)
    assert not any("INSERT INTO incident_events" in c for c in calls)


def test_resolution_alert_records_event(monkeypatch) -> None:
    monkeypatch.setattr(
        incidents,
        "settings",
        lambda: SimpleNamespace(alert_webhook_token="local-test-token"),
    )

    mock_conn = MagicMock()
    # Incident currently exists with status "firing"
    mock_conn.execute.return_value.fetchone.return_value = {
        "status": "firing",
        "started_at": sample_alert().startsAt,
        "resolved_at": None,
    }

    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=mock_conn)
    cm.__exit__ = MagicMock(return_value=False)

    mock_pool = MagicMock()
    mock_pool.connection.return_value = cm
    monkeypatch.setattr(incidents, "pool", lambda: mock_pool)

    resolved_alert = sample_alert()
    resolved_alert.status = "resolved"

    with TestClient(api.app) as client:
        resp = client.post(
            "/api/v1/internal/alertmanager",
            headers={"Authorization": "Bearer local-test-token"},
            json={"alerts": [resolved_alert.model_dump(mode="json")]},
        )
        assert resp.status_code == 200

    calls = [str(call) for call in mock_conn.execute.mock_calls]
    # Both UPDATE incidents and INSERT INTO incident_events were called
    assert any("UPDATE incidents" in c for c in calls)
    assert any("INSERT INTO incident_events" in c for c in calls)


def test_alert_timestamps_require_timezone_information():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        incidents.IncomingAlert(
            status="firing", fingerprint="a" * 16, startsAt=datetime(2026, 11, 24)
        )
