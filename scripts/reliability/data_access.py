"""Small, testable database and Redis privilege setup for local M6 observers."""

import re

from opsproof_control.database_permissions import grant_application_tables
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
    grant_application_tables(conn, username)


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
