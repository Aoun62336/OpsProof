"""Executor flags cannot manufacture independently verified hypotheses."""

from datetime import UTC, datetime, timedelta

import pytest

from scripts.m6.independent_hypothesis import establish
from scripts.m6.restricted_access import (
    mutation_rules,
    observer_dsn,
    read_rules,
    redis_url,
)


def state(scenario):
    now = datetime.now(UTC)
    return {
        "scenario": scenario,
        "observed": True,
        "dispatch_intent_at": (now - timedelta(seconds=10)).isoformat(),
        "cleanup_started_at": now.isoformat(),
    }


@pytest.mark.parametrize(
    "scenario",
    [
        "worker_saturation",
        "database_connectivity",
        "faulty_release",
        "worker_failure",
        "downstream_latency",
        "misleading_evidence",
    ],
)
def test_executor_success_flag_without_independent_samples_never_proves_success(
    scenario,
):
    assert establish(state(scenario), [], [], {}) is False


def test_database_effect_must_be_in_window_and_leave_control_healthy():
    value = state("database_connectivity")
    sample = {
        "at": datetime.now(UTC).isoformat(),
        "database_probe_status": 503,
        "database_probe_detail": "Fresh database connection unavailable",
        "control_ready": 200,
    }
    sample.update(
        {
            key: sample["at"]
            for key in (
                "database_probe_at",
                "database_probe_until",
                "control_ready_at",
                "control_ready_until",
            )
        }
    )
    assert not establish(value, [sample], [], {})
    sample["at"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
    sample.update(
        {
            key: sample["at"]
            for key in (
                "database_probe_at",
                "database_probe_until",
                "control_ready_at",
                "control_ready_until",
            )
        }
    )
    assert establish(value, [sample], [], {})
    sample["control_ready"] = 503
    assert not establish(value, [sample], [], {})


def test_unknown_queue_does_not_count_as_saturation():
    value = state("worker_saturation")
    sample = {
        "at": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
        "queue": {"lag": None},
    }
    jobs = [{"attempts": 1, "duration_ms": 2000}] * 60
    assert not establish(value, [sample], jobs, {"logs_relevant": True})
    sample["queue"]["lag"] = 11
    assert establish(value, [sample], jobs, {"logs_relevant": True})


def test_observer_role_has_no_secrets_mutation_exec_or_wildcards():
    for rule in read_rules():
        assert set(rule["verbs"]) <= {"get", "list"}
        assert "*" not in rule["apiGroups"] + rule["resources"] + rule["verbs"]
        assert not {"secrets", "pods/exec", "serviceaccounts/token"} & set(rule["resources"])


def test_worker_delete_permission_is_exact_and_cannot_patch_other_workloads():
    rules = mutation_rules("worker_failure", None, ["demo-worker-abc-xyz"])
    assert rules["opsproof-demo"] == [
        {
            "apiGroups": [""],
            "resources": ["pods"],
            "resourceNames": ["demo-worker-abc-xyz"],
            "verbs": ["delete"],
        }
    ]
    assert not rules["opsproof-control"]
    with pytest.raises(ValueError):
        mutation_rules("worker_failure", None, ["control-api-abc"])


def test_observers_refuse_default_or_remote_database_and_redis_credentials(monkeypatch):
    for variable, function, value in (
        (
            "OPSPROOF_M6_OBSERVER_DSN",
            observer_dsn,
            "postgresql://opsproof:any@127.0.0.1:18033/opsproof",
        ),
        ("OPSPROOF_M6_REDIS_URL", redis_url, "redis://remote.example:6379"),
    ):
        monkeypatch.delenv(variable, raising=False)
        with pytest.raises(ValueError):
            function()
        monkeypatch.setenv(variable, value)
        with pytest.raises(ValueError):
            function()
