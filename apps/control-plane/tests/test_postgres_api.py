"""Actual FastAPI auth, cookie/CSRF and ledger requests against disposable SQL."""

import json
import secrets
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import httpx2 as httpx
import pytest
from fastapi.testclient import TestClient
from psycopg.conninfo import make_conninfo
from psycopg.types.json import Jsonb
from scripts.reliability.data_access import grant_control_application
from test_postgres_safety import connect, dsn  # noqa: F401 - pytest fixture

from opsproof_control import api, auth, investigation_worker, model_provider, operations, trial_api
from opsproof_control.benchmark import CASES, make_snapshot
from opsproof_control.diagnosis import deterministic


def test_real_api_cookie_csrf_and_approval_contract(request, monkeypatch):
    database_url = request.getfixturevalue("dsn")
    username = "m6_app_" + uuid4().hex[:16]
    password = secrets.token_hex(24)
    with connect(database_url) as conn:
        grant_control_application(conn, username, password)
    application_url = make_conninfo(database_url, user=username, password=password)

    class Pool:
        def connection(self):
            return connect(application_url)

    key = uuid4().hex
    config = SimpleNamespace(
        api_key=key, secure_cookies=False, m6_enabled=True, m6_arm_enabled=False
    )
    monkeypatch.setattr(auth, "pool", Pool)
    monkeypatch.setattr(trial_api, "pool", Pool)
    monkeypatch.setattr(auth, "settings", lambda: config)
    monkeypatch.setattr(trial_api, "settings", lambda: config)
    with TestClient(api.app) as client:
        assert client.get("/api/v1/m6/trials").status_code == 401
        login = client.post("/api/v1/auth/login", json={"access_key": key})
        assert login.status_code == 200
        csrf = login.json()["csrf_token"]
        headers = {"Idempotency-Key": "m6-http-" + uuid4().hex}
        payload = {"scenario": "worker_failure", "source_revision": "38b3a46"}
        assert client.post("/api/v1/m6/trials", json=payload, headers=headers).status_code == 403
        headers["X-OpsProof-CSRF"] = "invalid"
        assert client.post("/api/v1/m6/trials", json=payload, headers=headers).status_code == 403
        headers["X-OpsProof-CSRF"] = csrf
        result = client.post("/api/v1/m6/trials", json=payload, headers=headers)
        assert result.status_code == 202
        trial = result.json()["id"]
        assert client.post("/api/v1/m6/trials", json=payload, headers=headers).json()["id"] == trial
        assert client.get(f"/api/v1/m6/trials/{trial}").json()["phase"] == "requested"
        assert len(client.get(f"/api/v1/m6/trials/{trial}/events").json()) == 1
        assert client.get(f"/api/v1/m6/trials/{trial}/artifacts").json() == []
        assert client.get(f"/api/v1/m6/trials/{trial}/verifications").json() == []
        assert (
            client.post(
                "/api/v1/m6/trials", headers=headers, json={**payload, "source_revision": "abcdef0"}
            ).status_code
            == 409
        )
        assert (
            client.post(
                "/api/v1/m6/trials",
                headers=headers,
                json={**payload, "scenario": "arbitrary_shell"},
            ).status_code
            == 422
        )
        assert (
            client.post(
                "/api/v1/m6/trials", headers=headers, json={**payload, "cleanup_verified": True}
            ).status_code
            == 422
        )
        for value in ("yes", 1, None):
            approval = {
                "confirmation": "ARM M6 LOCAL TRIAL",
                "approved_test_scope": value,
                "cleanup_plan_confirmed": True,
            }
            assert (
                client.post(
                    f"/api/v1/m6/trials/{trial}/arm", headers=headers, json=approval
                ).status_code
                == 422
            )
        approval["approved_test_scope"] = True
        assert (
            client.post(
                f"/api/v1/m6/trials/{trial}/arm", headers=headers, json=approval
            ).status_code
            == 403
        )
        assert (
            client.post(f"/api/v1/m6/trials/{trial}/abort", headers=headers).json()["phase"]
            == "aborted"
        )
        assert client.post(f"/api/v1/m6/trials/{trial}/abort", headers=headers).status_code == 409
        assert (
            client.post("/api/v1/auth/logout", headers={"X-OpsProof-CSRF": csrf}).status_code == 200
        )
        assert client.get("/api/v1/m6/trials").status_code == 401


@pytest.mark.parametrize("policy_mismatch", [False, True])
def test_ai_api_worker_persistence_without_provider_calls(request, monkeypatch, policy_mismatch):
    """Exercise real SQL/API/worker boundaries; intercept only the model transport."""
    database_url = request.getfixturevalue("dsn")
    username = "m6_app_" + uuid4().hex[:16]
    password = secrets.token_hex(24)
    with connect(database_url) as conn:
        grant_control_application(conn, username, password)
    application_url = make_conninfo(database_url, user=username, password=password)

    class Pool:
        def connection(self):
            return connect(application_url)

    key = secrets.token_hex(24)
    config = SimpleNamespace(
        api_key=key,
        ai_enabled=False,
        ai_daily_limit=10,
        ai_provider="nvidia",
        ai_model=model_provider.NVIDIA_MODEL,
        ai_api_key="intercepted-provider-fixture",
    )
    for module in (auth, operations, model_provider):
        monkeypatch.setattr(module, "settings", lambda: config)
    for module in (operations, investigation_worker):
        monkeypatch.setattr(module, "pool", Pool)
    snapshot = make_snapshot(CASES[0])
    fingerprint = uuid4().hex
    snapshot = snapshot.model_copy(update={"incident_fingerprint": fingerprint})
    baseline = deterministic(snapshot).model_dump()
    investigation = uuid4()
    with connect(database_url) as conn:
        conn.execute(
            "INSERT INTO incidents(fingerprint,name,target,severity,status,"
            "started_at,last_seen_at) "
            "VALUES (%s,%s,%s,'warning','firing',now(),now())",
            (fingerprint, snapshot.alert_name, snapshot.target),
        )
        conn.execute(
            "INSERT INTO investigations(id,request_key,incident_fingerprint,"
            "status,snapshot,baseline,"
            "completed_at) VALUES (%s,%s,%s,'ready',%s,%s,now())",
            (
                investigation,
                uuid4().hex,
                fingerprint,
                Jsonb(snapshot.model_dump(mode="json")),
                Jsonb(baseline),
            ),
        )
    answer = dict(baseline)
    if policy_mismatch:
        answer.update(cause="insufficient_evidence", action="none")
        assert answer != baseline
    factory = MagicMock()
    transport = factory.return_value.__enter__.return_value
    transport.post.return_value = httpx.Response(
        200,
        request=httpx.Request("POST", model_provider.NVIDIA_ENDPOINT),
        json={
            "model": model_provider.NVIDIA_SERVING_MODEL,
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps(answer)}}],
            "usage": {"prompt_tokens": 20, "completion_tokens": 30},
        },
    )
    monkeypatch.setattr(model_provider.httpx, "Client", factory)
    with TestClient(api.app) as client:
        endpoint = f"/api/v1/investigations/{investigation}/ai"
        assert client.post(endpoint).status_code == 401
        headers = {"X-OpsProof-Key": key}
        assert client.post(endpoint, headers=headers).status_code == 403
        factory.assert_not_called()
        config.ai_enabled = True
        assert client.post(endpoint, headers=headers).status_code == 202
        assert client.post(endpoint, headers=headers).json()["ai_status"] == "queued"
        investigation_worker.process_next_ai()
        rows = client.get(
            "/api/v1/investigations", params={"incident_fingerprint": fingerprint}, headers=headers
        ).json()
        assert len(rows) == 1
        row = rows[0]
        assert row["ai_status"] == ("failed" if policy_mismatch else "ready")
        if policy_mismatch:
            assert row["ai_result"] is None
            assert row["error"] == "AI evaluation failed: ValueError"
        else:
            assert row["ai_result"] == baseline
            assert row["ai_provider"] == "nvidia"
            assert row["ai_model"] == model_provider.NVIDIA_MODEL
            assert row["ai_usage"] == {"input_tokens": 20, "output_tokens": 30}
        investigation_worker.process_next_ai()
        assert transport.post.call_count == 1
        assert "intercepted-provider-fixture" not in json.dumps(row)
    with connect(database_url) as conn:
        assert (
            conn.execute(
                "SELECT count(*) AS n FROM recoveries WHERE investigation_id=%s", (investigation,)
            ).fetchone()["n"]
            == 0
        )
