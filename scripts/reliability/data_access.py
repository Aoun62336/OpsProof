"""Small, testable database and Redis privilege setup for local M6 observers."""

import re

from psycopg import sql


def grant_sql_observer(conn, username, password, tables):
    if not re.fullmatch(r"m6_read_[a-f0-9]{16}", username):
        raise ValueError("Owned M6 observer role required")
    if set(tables) not in (
        {"jobs"},
        {"incidents", "incident_events", "investigations"},
    ):
        raise ValueError("Unapproved observer table grants")
    role = sql.Identifier(username)
    database = sql.Identifier(conn.info.dbname)
    conn.execute(
        sql.SQL(
            "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}"
        ).format(role, sql.Literal(password))
    )
    conn.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(database, role))
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
    conn.execute(
        sql.SQL("GRANT SELECT ON {} TO {}").format(
            sql.SQL(",").join(sql.Identifier(table) for table in tables),
            role,
        )
    )


def revoke_sql_observer(conn, username, tables):
    if not re.fullmatch(r"m6_read_[a-f0-9]{16}", username):
        raise ValueError("Owned M6 observer role required")
    if not conn.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (username,)).fetchone():
        return
    role = sql.Identifier(username)
    for table in tables:
        conn.execute(sql.SQL("REVOKE ALL ON {} FROM {}").format(sql.Identifier(table), role))
    conn.execute(sql.SQL("REVOKE ALL ON SCHEMA public FROM {}").format(role))
    conn.execute(
        sql.SQL("REVOKE ALL ON DATABASE {} FROM {}").format(sql.Identifier(conn.info.dbname), role)
    )
    conn.execute(sql.SQL("DROP ROLE {}").format(role))


def configure_redis_observer(client, username, password, *, enqueue=False):
    if not re.fullmatch(r"m6_(observe|actuate)_[a-f0-9]{16}", username):
        raise ValueError("Owned M6 Redis identity required")
    if enqueue and not username.startswith("m6_actuate_"):
        raise ValueError("Read-only observers cannot enqueue")
    commands = ["+ping", "+xinfo|groups"]
    if enqueue:
        commands.append("+xadd")
    client.acl_setuser(
        username,
        enabled=True,
        reset=True,
        passwords=["+" + password],
        keys=["opsproof:jobs"],
        commands=commands,
    )


def grant_control_application(conn, username, password):
    """Nonowner app role: retain M4/M5 DML, deny M6 actuation/proof/DDL."""
    if not re.fullmatch(r"m6_app_[a-f0-9]{16}", username):
        raise ValueError("Owned M6 application role required")
    role = sql.Identifier(username)
    conn.execute(
        sql.SQL(
            "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
            "NOINHERIT NOREPLICATION NOBYPASSRLS PASSWORD {}"
        ).format(role, sql.Literal(password))
    )
    conn.execute(
        sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(conn.info.dbname), role)
    )
    conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(role))
    conn.execute(sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}").format(role))
    conn.execute(sql.SQL("GRANT USAGE,SELECT ON ALL SEQUENCES IN SCHEMA public TO {}").format(role))
    tables = conn.execute(
        "SELECT tablename FROM pg_tables WHERE schemaname='public' "
        "AND left(tablename,3)<>'m6_' AND tablename<>'alembic_version'"
    ).fetchall()
    for row in tables:
        table = row["tablename"] if isinstance(row, dict) else row[0]
        conn.execute(
            sql.SQL("GRANT INSERT,UPDATE,DELETE ON {} TO {}").format(sql.Identifier(table), role)
        )
    grants = [
        "INSERT (id,request_key,request_hash,scenario,target,source_revision) ON m6_trials",
        "UPDATE (phase,updated_at,approved_test_scope,cleanup_plan_confirmed,completed_at,error,"
        "abort_requested,approved_at,approval_expires_at) ON m6_trials",
        "INSERT ON m6_trial_events",
        "INSERT,UPDATE ON m6_trial_outbox",
        "INSERT,DELETE ON m6_target_leases",
        "INSERT,DELETE ON m6_execution_leases",
        "INSERT ON m6_reuse_observations",
    ]
    for grant in grants:
        conn.execute(sql.SQL("GRANT " + grant + " TO {}").format(role))


def revoke_control_application(conn, username):
    if not re.fullmatch(r"m6_app_[a-f0-9]{16}", username):
        raise ValueError("Owned M6 application role required")
    role = sql.Identifier(username)
    conn.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(role))
    columns = conn.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema='public' AND table_name='m6_trials'"
    ).fetchall()
    names = [row["column_name"] if isinstance(row, dict) else row[0] for row in columns]
    conn.execute(
        sql.SQL("REVOKE ALL ({}) ON m6_trials FROM {}").format(
            sql.SQL(",").join(sql.Identifier(name) for name in names),
            role,
        )
    )
    conn.execute(sql.SQL("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {}").format(role))
    conn.execute(sql.SQL("REVOKE ALL ON SCHEMA public FROM {}").format(role))
    conn.execute(
        sql.SQL("REVOKE ALL ON DATABASE {} FROM {}").format(sql.Identifier(conn.info.dbname), role)
    )
    conn.execute(sql.SQL("DROP ROLE {}").format(role))
