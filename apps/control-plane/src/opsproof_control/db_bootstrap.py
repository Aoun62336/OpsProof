"""Resumable database bootstrap and granular post-migration application grants.

Master credentials stay in bootstrap. Migration owns schema changes. Retrying
never rotates an existing role password or adopts an unrelated role.
"""

import argparse
import os
import sys

import psycopg
from alembic.config import Config
from psycopg import sql
from psycopg.rows import dict_row, tuple_row

from alembic import command

from .database_permissions import grant_application_tables
from .trial_access import require_application_role

APP_ROLE = "opsproof_app"
MIG_ROLE = "opsproof_migrate"
DB_NAME = "opsproof"
OWNERSHIP = "OpsProof managed database role v1"


def required(name: str) -> str:
    value = os.environ.get(name, "")
    if not value:
        raise ValueError(f"Required environment variable missing: {name}")
    return value


def conninfo(user: str, password: str) -> str:
    return psycopg.conninfo.make_conninfo(
        host=required("OPSPROOF_RDS_HOST"),
        port=int(os.environ.get("OPSPROOF_RDS_PORT", "5432")),
        dbname=DB_NAME,
        user=user,
        password=password,
        sslmode="verify-full",
        sslrootcert="/etc/opsproof/rds-ca/global-bundle.pem",
        connect_timeout=10,
    )


def provision(conn, app_password: str, mig_password: str) -> None:
    """Atomically create or reconcile only explicitly owned restricted roles."""
    if min(len(app_password), len(mig_password)) < 32 or app_password == mig_password:
        raise ValueError("Distinct generated passwords of at least 32 characters are required")
    with conn.transaction(), conn.cursor(row_factory=tuple_row) as cursor:
        for name, password in ((APP_ROLE, app_password), (MIG_ROLE, mig_password)):
            row = cursor.execute(
                "SELECT rolsuper,rolcreatedb,rolcreaterole,rolinherit,rolreplication,"
                "rolbypassrls,rolcanlogin,shobj_description(oid,'pg_authid') "
                "FROM pg_roles WHERE rolname=%s",
                (name,),
            ).fetchone()
            if row is None:
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                        "NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}"
                    ).format(sql.Identifier(name), sql.Literal(password))
                )
                cursor.execute(
                    sql.SQL("COMMENT ON ROLE {} IS {}").format(
                        sql.Identifier(name), sql.Literal(OWNERSHIP)
                    )
                )
            elif any(row[:6]) or not row[6] or row[7] != OWNERSHIP:
                raise RuntimeError("Existing role ownership or authority does not match")
            if cursor.execute(
                "SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member "
                "WHERE r.rolname=%s LIMIT 1",
                (name,),
            ).fetchone():
                raise RuntimeError("Managed role has unexpected role memberships")
        cursor.execute(
            sql.SQL("GRANT CONNECT ON DATABASE {} TO {}, {}").format(
                sql.Identifier(conn.info.dbname), sql.Identifier(APP_ROLE), sql.Identifier(MIG_ROLE)
            )
        )
        cursor.execute("REVOKE CREATE ON SCHEMA public FROM PUBLIC")
        cursor.execute(
            sql.SQL("GRANT USAGE ON SCHEMA public TO {}, {}").format(
                sql.Identifier(APP_ROLE), sql.Identifier(MIG_ROLE)
            )
        )
        cursor.execute(
            sql.SQL("GRANT CREATE ON SCHEMA public TO {}").format(sql.Identifier(MIG_ROLE))
        )
        cursor.execute(
            sql.SQL("REVOKE CREATE ON SCHEMA public FROM {}").format(sql.Identifier(APP_ROLE))
        )


def migrate(config_path: str = "alembic.ini") -> None:
    """Migrate as the dedicated role, then restore granular application authority."""
    database_url = required("OPSPROOF_CONTROL_DATABASE_URL")
    fields = psycopg.conninfo.conninfo_to_dict(database_url)
    if fields.get("user") != MIG_ROLE or fields.get("sslmode") != "verify-full":
        raise ValueError("Cloud migration requires the dedicated role and verified TLS")
    with psycopg.connect(database_url) as connection:
        if connection.execute("SELECT current_user").fetchone()[0] != MIG_ROLE:
            raise RuntimeError("Unexpected migration identity")
    command.upgrade(Config(config_path), "head")
    with psycopg.connect(database_url) as connection:
        grant_application_tables(connection, APP_ROLE, reset=True)


def verify() -> None:
    with psycopg.connect(
        conninfo(APP_ROLE, required("OPSPROOF_CLOUD_APP_PASSWORD")), row_factory=dict_row
    ) as connection:
        if connection.execute("SELECT current_user").fetchone()["current_user"] != APP_ROLE:
            raise RuntimeError("Unexpected application identity")
        if connection.execute("SELECT to_regclass('public.m6_trials') AS ledger").fetchone()[
            "ledger"
        ]:
            require_application_role(connection)
        elif connection.execute(
            "SELECT has_schema_privilege(current_user,'public','CREATE') AS unsafe"
        ).fetchone()["unsafe"]:
            raise RuntimeError("Application role has schema creation authority")
    with psycopg.connect(
        conninfo(MIG_ROLE, required("OPSPROOF_CLOUD_MIGRATION_PASSWORD"))
    ) as connection:
        row = connection.execute(
            "SELECT current_user,has_schema_privilege(current_user,'public','CREATE')"
        ).fetchone()
        if row != (MIG_ROLE, True):
            raise RuntimeError("Unexpected migration identity or schema authority")
    print("CLOUD_DB_ROLES_VERIFIED (no credentials disclosed)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("bootstrap", "migrate", "verify"), required=True)
    parser.add_argument("--alembic-config", default="alembic.ini")
    args = parser.parse_args()
    if args.mode == "bootstrap":
        with psycopg.connect(
            conninfo(
                required("OPSPROOF_RDS_MASTER_USERNAME"), required("OPSPROOF_RDS_MASTER_PASSWORD")
            ),
            autocommit=True,
        ) as connection:
            provision(
                connection,
                required("OPSPROOF_CLOUD_APP_PASSWORD"),
                required("OPSPROOF_CLOUD_MIGRATION_PASSWORD"),
            )
        verify()
    elif args.mode == "migrate":
        migrate(args.alembic_config)
    else:
        verify()


if __name__ == "__main__":
    try:
        main()
    except (ValueError, psycopg.Error, RuntimeError) as exc:
        print(f"CLOUD_DB_BOOTSTRAP_FAILED: {type(exc).__name__}", file=sys.stderr)
        raise SystemExit(1) from None
