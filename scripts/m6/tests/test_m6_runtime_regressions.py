"""Regressions for failures found during actual local acceptance execution."""

from contextlib import nullcontext
from copy import deepcopy

import psycopg
import pytest

from scripts.m6.local_environment import LocalEnvironment
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
