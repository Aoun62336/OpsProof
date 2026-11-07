"""Add investigations, controlled recovery and audit records.

Revision ID: 0004
Revises: 0003
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investigations",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("request_key", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "incident_fingerprint",
            sa.String(64),
            sa.ForeignKey("incidents.fingerprint"),
            nullable=False,
        ),
        sa.Column("run_id", sa.UUID(), sa.ForeignKey("experiments.id")),
        sa.Column("status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("snapshot", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("baseline", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ai_status", sa.Text(), nullable=False, server_default="not_requested"),
        sa.Column("ai_result", JSONB()),
        sa.Column("ai_provider", sa.Text()),
        sa.Column("ai_model", sa.Text()),
        sa.Column("ai_usage", JSONB()),
        sa.Column("ai_elapsed_ms", sa.Integer()),
        sa.Column("ai_requested_at", sa.DateTime(timezone=True)),
        sa.Column("ai_started_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('queued','running','ready','failed')"),
        sa.CheckConstraint("ai_status IN ('not_requested','queued','running','ready','failed')"),
    )
    op.create_index("ix_investigations_incident", "investigations", ["incident_fingerprint"])
    op.create_table(
        "recoveries",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("request_key", sa.Text(), nullable=False, unique=True),
        sa.Column(
            "investigation_id", sa.UUID(), sa.ForeignKey("investigations.id"), nullable=False
        ),
        sa.Column(
            "incident_fingerprint",
            sa.String(64),
            sa.ForeignKey("incidents.fingerprint"),
            nullable=False,
        ),
        sa.Column("run_id", sa.UUID(), sa.ForeignKey("experiments.id"), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending_approval"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("verify_by", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("result", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error", sa.Text()),
        sa.CheckConstraint("action = 'resume_demo_worker'"),
        sa.CheckConstraint(
            "status IN ('pending_approval','approved','running','verifying',"
            "'succeeded','failed','rejected','expired','indeterminate')"
        ),
    )
    op.create_index(
        "ix_recoveries_active_incident",
        "recoveries",
        ["incident_fingerprint"],
        unique=True,
        postgresql_where=sa.text("status IN ('pending_approval','approved','running','verifying')"),
    )
    op.create_table(
        "recovery_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("recovery_id", sa.UUID(), sa.ForeignKey("recoveries.id"), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("details", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("ix_recovery_events_recovery", "recovery_events", ["recovery_id"])


def downgrade() -> None:
    op.drop_table("recovery_events")
    op.drop_table("recoveries")
    op.drop_table("investigations")
