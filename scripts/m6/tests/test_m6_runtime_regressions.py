"""Regressions for failures found during actual local acceptance execution."""

import json
from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace

import psycopg
import pytest

from scripts.m6 import local_environment
from scripts.m6.local_environment import GIB, LocalEnvironment
from scripts.m6.restricted_access import RestrictedAccess


@pytest.mark.parametrize(
    "decision", [b"This user has no permissions to run the 'set' command", "NOPERM"]
)
def test_redis_dryrun_text_denial_is_validated(tmp_path, monkeypatch, decision):
    run_permission_check(tmp_path, monkeypatch, decision)
    assert (tmp_path / "restricted-permission-checks.json").exists()


@pytest.mark.parametrize("decision", [b"OK", "OK", "unexpected", None, True])
def test_redis_dryrun_allow_or_unknown_fails_closed(tmp_path, monkeypatch, decision):
    with pytest.raises(RuntimeError, match="unexpectedly permits"):
        run_permission_check(tmp_path, monkeypatch, decision)
    assert not (tmp_path / "restricted-permission-checks.json").exists()


def run_permission_check(tmp_path, monkeypatch, decision):
    class SQL:
        def execute(self, statement):
            if statement.startswith("UPDATE"):
                raise psycopg.errors.InsufficientPrivilege()

        def transaction(self):
            return nullcontext()

    class Redis:
        def acl_dryrun(self, *_args):
            return decision

    access = object.__new__(RestrictedAccess)
    access.db_dsn = "unused"
    access.redis_users = ["test"]
    access.directory = tmp_path
    monkeypatch.setattr(access, "verify_kubernetes_permissions", lambda: [])
    monkeypatch.setattr(
        "scripts.m6.restricted_access.psycopg.connect", lambda *_a, **_k: nullcontext(SQL())
    )
    monkeypatch.setattr("scripts.m6.restricted_access.Redis", lambda **_k: nullcontext(Redis()))
    access.verify_permissions()


def test_already_restored_source_is_idempotent_but_foreign_changes_are_refused(monkeypatch):
    original = {
        "metadata": {"uid": "original", "resourceVersion": "1"},
        "spec": {"source": {"helm": {"parameters": [{"name": "fixture", "value": "false"}]}}},
    }
    env = object.__new__(LocalEnvironment)
    current = deepcopy(original)
    monkeypatch.setattr(env, "get", lambda *_a: current)

    def forbidden(*_a, **_k):
        raise AssertionError("No mutation of an already restored or foreign source")

    monkeypatch.setattr(env, "command", forbidden)
    assert env.restore_demo(original, [{"name": "fixture", "value": "true"}]) == current
    current["metadata"]["uid"] = "replacement"
    with pytest.raises(RuntimeError, match="ownership changed"):
        env.restore_demo(original, [])
    current["metadata"]["uid"] = "original"
    current["spec"]["source"]["helm"]["parameters"] = [{"name": "foreign", "value": "change"}]
    with pytest.raises(RuntimeError, match="ownership changed"):
        env.restore_demo(original, [])


@pytest.mark.parametrize(
    "change", [None, "low_host_ram", "low_node_ram", "foreign_node", "not_ready"]
)
def test_active_preflight_uses_live_capacity_and_retains_resource_boundaries(monkeypatch, change):
    node = {
        "metadata": {"name": "k3d-opsproof-server-0"},
        "status": {
            "capacity": {"memory": "10185332Ki", "cpu": "6"},
            "conditions": [{"type": "Ready", "status": "True"}],
        },
    }
    if change == "low_node_ram":
        node["status"]["capacity"]["memory"] = "1024Ki"
    elif change == "foreign_node":
        node["metadata"]["name"] = "unrelated-node"
    elif change == "not_ready":
        node["status"]["conditions"][0]["status"] = "False"
    monkeypatch.setattr(
        local_environment, "memory_available", lambda: GIB if change == "low_host_ram" else 3 * GIB
    )
    monkeypatch.setattr(
        local_environment.shutil, "disk_usage", lambda _: SimpleNamespace(free=20 * GIB)
    )
    monkeypatch.setattr(local_environment, "local_prefix", lambda _: ["kubectl"])

    def query(args):
        assert args == ["kubectl", "get", "nodes", "-o", "json"]
        return {"exit_code": 0, "output": json.dumps({"items": [node]})}

    monkeypatch.setattr(local_environment, "command", query)
    result = local_environment.resource_preflight()
    assert result["passed"] is (change is None)
    assert result["minimum_host_free_bytes"] == 2 * GIB
    assert result["minimum_disk_free_bytes"] == 15 * GIB
    assert result["emergency_stop_free_bytes"] == GIB
