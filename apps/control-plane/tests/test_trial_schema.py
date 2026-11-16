"""Schema contract checks; actual PostgreSQL migration requires a live test DB."""

from pathlib import Path


def test_schema_is_additive_and_has_independent_verification_checks():
    path = Path(__file__).resolve().parents[1] / "alembic/versions/0006_m6_trials.py"
    schema = path.read_text(encoding="utf-8")
    for table in (
        "m6_trials",
        "m6_trial_events",
        "m6_target_leases",
        "m6_trial_outbox",
        "m6_trial_artifacts",
    ):
        assert f"CREATE TABLE {table}" in schema
    assert "CONSTRAINT m6_success_requires_proof" in schema
    assert "CREATE UNIQUE INDEX ux_m6_active_target" in schema
    for existing in ("experiments", "incidents", "kubernetes_recoveries"):
        assert f"DROP TABLE {existing}" not in schema
        assert f"ALTER TABLE {existing}" not in schema
