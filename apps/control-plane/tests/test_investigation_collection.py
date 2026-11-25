"""Replica-aware evidence collection without a live Prometheus or provider."""

from time import time
from types import SimpleNamespace
from unittest.mock import MagicMock

import httpx2 as httpx
import pytest

from opsproof_control import investigation_worker as worker


def sample(instance, value, *, name=None):
    labels = {"job": "opsproof-demo-api", "instance": instance}
    if name:
        labels["__name__"] = name
    return {"metric": labels, "value": [1000, str(value)]}


@pytest.mark.parametrize("replicas", [1, 2, 4])
def test_every_healthy_recent_replica_is_accepted(replicas):
    up = [sample(str(i), 1, name="up") for i in range(replicas)]
    stamps = [sample(str(i), 990) for i in reversed(range(replicas))]
    assert worker.scrapes_fresh([up, stamps], 1000)


@pytest.mark.parametrize("stamp", [969, 1001, float("nan"), float("inf")])
def test_bad_time_never_establishes_freshness(stamp):
    vectors = [[sample("a", 1), sample("b", 1)], [sample("a", 990), sample("b", stamp)]]
    if stamp != stamp or stamp == float("inf"):
        with pytest.raises(ValueError):
            worker.scrapes_fresh(vectors, 1000)
    else:
        assert not worker.scrapes_fresh(vectors, 1000)


def test_one_failed_replica_prevents_positive_evidence():
    assert not worker.scrapes_fresh(
        [[sample("a", 1), sample("b", 0)], [sample("a", 990), sample("b", 990)]], 1000
    )


@pytest.mark.parametrize(
    "vectors",
    [
        [[], []],
        [[sample("a", 1)], [sample("b", 990)]],
        [[sample("a", 1), sample("a", 1)], [sample("a", 990)]],
        [[sample("a", 1)], []],
    ],
)
def test_absent_duplicate_or_changed_targets_are_unknown(vectors):
    with pytest.raises(ValueError):
        worker.scrapes_fresh(vectors, 1000)


def test_collection_joins_real_prometheus_vector_response(monkeypatch):
    monkeypatch.setattr(
        worker,
        "settings",
        lambda: SimpleNamespace(
            target_url="http://demo.invalid",
            inspection_key="fixture",
            prometheus_url="http://metrics.invalid",
        ),
    )
    now = time()
    responses = [
        {},
        {"queued": 2, "processing": 0},
        {"paused": True, "ttl_seconds": 120},
        {
            "status": "success",
            "data": {"resultType": "vector", "result": [sample("a", 1), sample("b", 1)]},
        },
        {
            "status": "success",
            "data": {"resultType": "vector", "result": [sample("b", now), sample("a", now)]},
        },
    ]
    client = MagicMock()
    client.get.side_effect = [
        httpx.Response(200, request=httpx.Request("GET", "http://fixture.invalid"), json=data)
        for data in responses
    ]
    factory = MagicMock()
    factory.return_value.__enter__.return_value = client
    monkeypatch.setattr(worker.httpx, "Client", factory)
    result = worker.collect(
        {
            "fingerprint": "a" * 16,
            "name": "OpsProofDemoQueueBacklog",
            "target": "opsproof-demo-api",
            "status": "firing",
        },
        None,
    )
    assert result.scrape_fresh is True
    assert result.queued == 2
    assert not result.errors
