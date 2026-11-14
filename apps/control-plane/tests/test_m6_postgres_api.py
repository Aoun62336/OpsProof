"""Actual FastAPI auth, cookie/CSRF and ledger requests against disposable SQL."""

import secrets
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from psycopg.conninfo import make_conninfo
from scripts.m6.data_access import grant_control_application
from test_m6_postgres_safety import connect, dsn  # noqa: F401 - pytest fixture

from opsproof_control import api, auth, m6_trial_api


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
    monkeypatch.setattr(m6_trial_api, "pool", Pool)
    monkeypatch.setattr(auth, "settings", lambda: config)
    monkeypatch.setattr(m6_trial_api, "settings", lambda: config)
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
