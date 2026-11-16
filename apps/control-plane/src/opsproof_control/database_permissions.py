"""Shared table authority for the local and managed-database application roles.

Application processes may update ordinary operational state, but cannot author
independent trial proof, dispatch acknowledgments or immutable artifacts.
"""

import re

from psycopg import sql


def grant_application_tables(conn, username, *, reset=False):
    """Apply the same granular contract after migrations, as the table owner."""
    if username != "opsproof_app" and not re.fullmatch(r"m6_app_[a-f0-9]{16}", username):
        raise ValueError("An owned OpsProof application role is required")
    role = sql.Identifier(username)
    if reset:
        conn.execute(sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA public FROM {}").format(role))
        columns = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_schema='public' AND table_name='m6_trials'"
        ).fetchall()
        names = [row["column_name"] if isinstance(row, dict) else row[0] for row in columns]
        if names:
            conn.execute(
                sql.SQL("REVOKE ALL ({}) ON m6_trials FROM {}").format(
                    sql.SQL(",").join(sql.Identifier(name) for name in names), role
                )
            )
        conn.execute(sql.SQL("REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM {}").format(role))
        conn.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM {}"
            ).format(role)
        )
        conn.execute(
            sql.SQL(
                "ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM {}"
            ).format(role)
        )
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
