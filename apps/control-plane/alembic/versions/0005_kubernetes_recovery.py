"""Separate typed Kubernetes recovery approvals and independent observations."""

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
    CREATE TABLE kubernetes_observations (
      name text PRIMARY KEY CHECK (name='demo-worker'),
      observed_at timestamptz NOT NULL,
      resource jsonb NOT NULL,
      telemetry jsonb NOT NULL
    );
    CREATE TABLE kubernetes_recoveries (
      id uuid PRIMARY KEY,
      request_key text NOT NULL UNIQUE,
      action text NOT NULL CHECK (action='restore_demo_worker'),
      incident_fingerprint varchar(64) NOT NULL REFERENCES incidents(fingerprint),
      run_id uuid NOT NULL REFERENCES experiments(id),
      status text NOT NULL CHECK (status IN (
        'pending_approval','approved','running','verifying',
        'succeeded','failed','expired','indeterminate')),
      target_uid text NOT NULL,
      target_version text NOT NULL,
      target_image text NOT NULL,
      job_ids jsonb NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      expires_at timestamptz NOT NULL,
      approved_at timestamptz,
      started_at timestamptz,
      completed_at timestamptz,
      result jsonb NOT NULL DEFAULT '{}',
      error text
    );
    CREATE TABLE kubernetes_recovery_events (
      id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      recovery_id uuid NOT NULL REFERENCES kubernetes_recoveries(id),
      type text NOT NULL,
      details jsonb NOT NULL DEFAULT '{}',
      created_at timestamptz NOT NULL DEFAULT now()
    );
    CREATE INDEX ix_kubernetes_recovery_status ON kubernetes_recoveries(status);
    """)


def downgrade():
    op.drop_table("kubernetes_recovery_events")
    op.drop_table("kubernetes_recoveries")
    op.drop_table("kubernetes_observations")
