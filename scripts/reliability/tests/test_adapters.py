"""Offline safety checks; these never stand in for six live scenario results."""

from copy import deepcopy
from pathlib import Path

import pytest

from scripts.reliability import run_local_trial
from scripts.reliability.contracts import Scenario
from scripts.reliability.scenario_adapters import ADAPTERS, database_exclusion, selected


def policies():
    return [
        {
            "metadata": {"name": "opsproof-default-deny"},
            "spec": {"podSelector": {}, "policyTypes": ["Ingress", "Egress"]},
        },
        {
            "metadata": {"name": "opsproof-namespace-traffic"},
            "spec": {"podSelector": {}, "ingress": [{"from": [{"podSelector": {}}]}]},
        },
    ]


LABELS = {
    "app.kubernetes.io/name": "opsproof-postgres",
    "app.kubernetes.io/instance": "demo-deps",
}


def test_exactly_six_adapters_and_no_arbitrary_target_factory():
    assert set(ADAPTERS) == {scenario.value for scenario in Scenario}
    assert all(
        adapter.target_resource[2] in ("opsproof-demo", "opsproof-observability")
        for adapter in ADAPTERS.values()
    )


def test_additive_database_isolation_excludes_only_postgres():
    original, exclusion = database_exclusion(policies(), LABELS)
    assert original["spec"]["podSelector"] == {}
    assert not selected(LABELS, exclusion)
    assert selected({"app.kubernetes.io/name": "opsproof-redis"}, exclusion)
    assert selected({"opsproof.io/role": "api"}, exclusion)


@pytest.mark.parametrize(
    "change", ["extra_allow", "wrong_database", "gitops_owner", "unknown_selector"]
)
def test_database_fault_refuses_unreviewed_additive_or_ownership_conditions(change):
    rules = deepcopy(policies())
    labels = dict(LABELS)
    if change == "extra_allow":
        rules.append({"metadata": {"name": "another-allow"}, "spec": {"podSelector": {}}})
    elif change == "wrong_database":
        labels["app.kubernetes.io/instance"] = "control-deps"
    elif change == "gitops_owner":
        rules[1]["metadata"]["annotations"] = {"argocd.argoproj.io/tracking-id": "owned"}
    else:
        rules[1]["spec"]["podSelector"] = {
            "matchExpressions": [{"key": "x", "operator": "Unknown"}]
        }
    with pytest.raises(ValueError):
        database_exclusion(rules, labels)


def test_missing_acknowledgment_never_reaches_preflight(monkeypatch):
    def unexpected():
        raise AssertionError("Must not inspect or mutate any runtime")

    monkeypatch.setattr(run_local_trial, "resource_preflight", unexpected)
    with pytest.raises(ValueError):
        run_local_trial.execute("worker_failure", "yes")


def test_resource_blocker_never_reads_credentials_or_constructs_an_actuator(tmp_path, monkeypatch):
    monkeypatch.setattr(run_local_trial, "ROOT", tmp_path)
    monkeypatch.setattr(
        run_local_trial,
        "resource_preflight",
        lambda: {"passed": False, "blockers": ["Host free RAM below 5 GiB"]},
    )
    monkeypatch.setattr(
        run_local_trial, "source_identity", lambda: {"head": "a" * 40, "dirty": True}
    )

    def unexpected(*_args, **_kwargs):
        raise AssertionError("Blocked preflight must not construct an actuator or read .env")

    monkeypatch.setattr(run_local_trial, "LocalEnvironment", unexpected)
    monkeypatch.setattr(run_local_trial, "read_env", unexpected)
    result = run_local_trial.execute("worker_failure", "M6_LOCAL_FAULT_TRIAL")
    assert result["status"] == "BLOCKED" and result["fault_sent"] is False
    assert "injected_at_utc" not in result
    assert len(list(Path(tmp_path).glob(".runtime/m6/trials/*/result.json"))) == 1
