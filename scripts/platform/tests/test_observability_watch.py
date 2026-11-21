import argparse
import json
from datetime import UTC, datetime

import pytest

from scripts.platform.watch_observability import EXPECTED, inspect, loopback


@pytest.mark.parametrize(
    "url",
    [
        "http://example.com:80",
        "http://token@localhost:80",
        "http://localhost",
        "http://127.0.0.1:80/?key=secret",
    ],
)
def test_watch_refuses_remote_or_credential_urls(url):
    with pytest.raises(argparse.ArgumentTypeError):
        loopback(url)


def evidence(*, missing=None, stale=False, critical=False):
    now = datetime.now(UTC).timestamp()
    rows = [
        {
            "labels": {"job": job},
            "health": "up",
            "lastScrape": datetime.fromtimestamp(now - (40 if stale else 1), UTC).isoformat(),
        }
        for job in EXPECTED
        if job != missing
    ]

    def getter(url):
        if url.endswith("/api/v1/targets"):
            return json.dumps({"status": "success", "data": {"activeTargets": rows}}).encode()
        if url.endswith("/api/v2/alerts"):
            return json.dumps(
                [
                    {
                        "labels": {"severity": "critical", "alertname": "test"},
                        "status": {"state": "active"},
                    }
                ]
                if critical
                else []
            ).encode()
        return b"ready"

    return getter, now


def test_watch_is_independent_of_control_api_and_fails_on_missing_target():
    getter, now = evidence(missing="opsproof-control-api")
    result = inspect("http://127.0.0.1:1", "http://127.0.0.1:2", getter=getter, now=now)
    assert not result["healthy"]
    assert "opsproof-control-api" in " ".join(result["failures"])


@pytest.mark.parametrize("options", [{}, {"stale": True}, {"critical": True}])
def test_watch_checks_freshness_and_active_critical_alerts(options):
    getter, now = evidence(**options)
    result = inspect("http://127.0.0.1:1", "http://127.0.0.1:2", getter=getter, now=now)
    assert result["healthy"] == (not options)


def test_monitoring_outage_cannot_be_reported_healthy():
    def unavailable(_):
        raise TimeoutError()

    result = inspect("http://127.0.0.1:1", "http://127.0.0.1:2", getter=unavailable)
    assert not result["healthy"] and len(result["failures"]) == 4
