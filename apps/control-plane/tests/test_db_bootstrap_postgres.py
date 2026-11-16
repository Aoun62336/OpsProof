"""Real TLS PostgreSQL role/bootstrap regressions in an explicitly owned test server."""

import os
import secrets
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import quote, urlsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from psycopg.rows import dict_row
from test_trial_postgres_integration import _test_dsn

from opsproof_control import db_bootstrap as bootstrap
from opsproof_control.trial_access import require_application_role
from opsproof_control.trial_catalog import Scenario
from opsproof_control.trial_store import create_trial, request_abort

ROOT = Path(__file__).resolve().parents[3]


def role_url(dsn, username, password):
    parsed = urlsplit(dsn)
    return parsed._replace(netloc=f"{username}:{quote(password, safe='')}@127.0.0.1:15432").geturl()


@pytest.fixture(scope="module")
def cloud_database():
    if not os.environ.get("OPSPROOF_CLOUD_TEST_DATABASE_URL"):
        pytest.skip("Requires the owned --cloud TLS PostgreSQL runner")
    parent = _test_dsn()
    assert parent == os.environ["OPSPROOF_CLOUD_TEST_DATABASE_URL"]
    assert "sslmode=verify-full" in parent
    dsn = urlsplit(parent)._replace(path="/opsproof").geturl()
    app_password, migration_password = secrets.token_hex(24), secrets.token_hex(24)
    with psycopg.connect(parent, autocommit=True) as admin:
        if admin.execute("SELECT 1 FROM pg_database WHERE datname='opsproof'").fetchone():
            pytest.fail("Refusing to adopt an existing cloud fixture database")
        if admin.execute(
            "SELECT 1 FROM pg_roles WHERE rolname IN ('opsproof_app','opsproof_migrate')"
        ).fetchone():
            pytest.fail("Refusing to adopt existing cloud fixture roles")
        admin.execute("CREATE DATABASE opsproof")
    try:
        with psycopg.connect(dsn, autocommit=True) as owner:
            bootstrap.provision(owner, app_password, migration_password)
        yield SimpleNamespace(
            admin=dsn,
            app=role_url(dsn, "opsproof_app", app_password),
            migration=role_url(dsn, "opsproof_migrate", migration_password),
            app_password=app_password,
            migration_password=migration_password,
            tls=Path(os.environ["OPSPROOF_CLOUD_TEST_TLS_DIRECTORY"]),
        )
    finally:
        with psycopg.connect(parent, autocommit=True) as owner:
            owner.execute("DROP DATABASE opsproof WITH (FORCE)")
            owner.execute("DROP ROLE IF EXISTS opsproof_app")
            owner.execute("DROP ROLE IF EXISTS opsproof_migrate")


def test_bootstrap_retry_preserves_owned_passwords(cloud_database):
    data = cloud_database
    with psycopg.connect(data.admin, autocommit=True) as owner:
        bootstrap.provision(owner, data.app_password, data.migration_password)
        bootstrap.provision(owner, secrets.token_hex(24), secrets.token_hex(24))
    with psycopg.connect(data.app) as app:
        assert app.execute("SELECT current_user").fetchone()[0] == "opsproof_app"
    with psycopg.connect(data.migration) as migration:
        assert migration.execute("SELECT current_user").fetchone()[0] == "opsproof_migrate"


def test_bootstrap_refuses_authority_or_ownership_drift(cloud_database):
    data = cloud_database
    with psycopg.connect(data.admin, autocommit=True) as owner:
        owner.execute("ALTER ROLE opsproof_app CREATEDB")
        try:
            with pytest.raises(RuntimeError, match="ownership or authority"):
                bootstrap.provision(owner, data.app_password, data.migration_password)
        finally:
            owner.execute("ALTER ROLE opsproof_app NOCREATEDB")
        owner.execute("COMMENT ON ROLE opsproof_app IS 'unrelated owner'")
        try:
            with pytest.raises(RuntimeError, match="ownership or authority"):
                bootstrap.provision(owner, data.app_password, data.migration_password)
        finally:
            owner.execute(
                sql.SQL("COMMENT ON ROLE opsproof_app IS {}").format(
                    sql.Literal(bootstrap.OWNERSHIP)
                )
            )


def test_interrupted_second_role_creation_rolls_back_first(cloud_database, monkeypatch):
    app = "opsproof_interrupt_app_" + uuid4().hex[:8]
    migration = "opsproof_interrupt_migrate_" + uuid4().hex[:8]
    monkeypatch.setattr(bootstrap, "APP_ROLE", app)
    monkeypatch.setattr(bootstrap, "MIG_ROLE", migration)
    with psycopg.connect(cloud_database.admin, autocommit=True) as owner:

        class FailingCursor:
            def __init__(self, raw):
                self.raw, self.creates = raw, 0

            def __enter__(self):
                self.raw.__enter__()
                return self

            def __exit__(self, *args):
                return self.raw.__exit__(*args)

            def execute(self, query, parameters=None):
                text = query.as_string(owner) if hasattr(query, "as_string") else query
                if text.startswith("CREATE ROLE"):
                    self.creates += 1
                    if self.creates == 2:
                        raise RuntimeError("Injected second-role interruption")
                return self.raw.execute(query, parameters)

        proxy = SimpleNamespace(
            info=owner.info,
            transaction=owner.transaction,
            cursor=lambda **kwargs: FailingCursor(owner.cursor(**kwargs)),
        )
        with pytest.raises(RuntimeError, match="second-role interruption"):
            bootstrap.provision(proxy, secrets.token_hex(24), secrets.token_hex(24))
        assert (
            owner.execute(
                "SELECT rolname FROM pg_roles WHERE rolname=ANY(%s)", ([app, migration],)
            ).fetchall()
            == []
        )


def test_real_migration_and_repair_keep_independent_proof_restricted(cloud_database):
    data = cloud_database
    env = {**os.environ, "OPSPROOF_CONTROL_DATABASE_URL": data.migration}
    args = [
        sys.executable,
        "-m",
        "opsproof_control.db_bootstrap",
        "--mode",
        "migrate",
        "--alembic-config",
        str(ROOT / "apps/control-plane/alembic.ini"),
    ]
    subprocess.run(args, cwd=ROOT, env=env, check=True, capture_output=True, timeout=60)
    # Reproduce the supplied unsafe grants and repair them through the normal entry point.
    with psycopg.connect(data.migration) as migration:
        migration.execute(
            "GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA public TO opsproof_app"
        )
        migration.execute(
            "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT "
            "INSERT,UPDATE,DELETE ON TABLES TO opsproof_app"
        )
    subprocess.run(args, cwd=ROOT, env=env, check=True, capture_output=True, timeout=60)
    with psycopg.connect(data.app, row_factory=dict_row) as app:
        require_application_role(app)
        trial, _ = create_trial(
            app,
            request_key="cloud-permissions-" + uuid4().hex,
            scenario=Scenario.MISLEADING_EVIDENCE,
            source_revision="a" * 40,
        )
        assert request_abort(app, trial["id"])["phase"] == "aborted"
        for denied in [
            "INSERT INTO m6_trial_verifications DEFAULT VALUES",
            "INSERT INTO m6_trial_artifacts DEFAULT VALUES",
            "UPDATE m6_trials SET independent_verified=true",
            "CREATE TABLE should_never_exist(id integer)",
        ]:
            with pytest.raises(psycopg.errors.InsufficientPrivilege), app.transaction():
                app.execute(denied)


def test_tls_requires_trusted_ca_hostname_and_encryption(cloud_database):
    data = cloud_database
    with psycopg.connect(data.admin) as connection:
        assert connection.execute(
            "SELECT ssl FROM pg_stat_ssl WHERE pid=pg_backend_pid()"
        ).fetchone()[0]
    with pytest.raises(psycopg.OperationalError):
        psycopg.connect(data.admin, sslrootcert=str(data.tls / "wrong.crt"), connect_timeout=2)
    with pytest.raises(psycopg.OperationalError):
        psycopg.connect(
            data.admin, host="untrusted.invalid", hostaddr="127.0.0.1", connect_timeout=2
        )
    with pytest.raises(psycopg.OperationalError):
        psycopg.connect(data.admin, sslmode="disable", connect_timeout=2)
