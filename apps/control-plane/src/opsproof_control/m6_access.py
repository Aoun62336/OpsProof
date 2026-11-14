"""M6 web/coordinator database access must be nonowner and unable to forge proof."""

from psycopg import Connection


def require_application_role(conn: Connection) -> None:
    row = conn.execute("""
        SELECT r.rolsuper OR r.rolcreaterole OR r.rolbypassrls
          OR has_schema_privilege(current_user,'public','CREATE')
          OR has_table_privilege(current_user,'public.m6_trial_verifications','INSERT')
          OR has_column_privilege(current_user,'public.m6_trials','independent_verified','UPDATE')
          OR has_column_privilege(current_user,'public.m6_trials','injection_acknowledged','UPDATE')
          OR has_table_privilege(current_user,'public.m6_trial_events','TRUNCATE') AS unsafe
        FROM pg_roles r WHERE rolname=current_user
    """).fetchone()
    if not row or row["unsafe"]:
        raise PermissionError("M6 requires a restricted nonowner database role")
