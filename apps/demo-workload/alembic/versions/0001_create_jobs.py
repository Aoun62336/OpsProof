"""Create the initial durable job and outbox tables.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column(
            "idempotency_key",
            sa.Text(),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default="queued",
        ),
        sa.Column(
            "duration_ms",
            sa.Integer(),
            nullable=False,
        ),
        sa.Column(
            "attempts",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("worker_token", sa.UUID()),
        sa.Column(
            "lease_until",
            sa.DateTime(timezone=True),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
        ),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
        ),
        sa.CheckConstraint(
            "status IN ('queued', 'processing', 'completed', 'failed')",
            name="ck_job_status",
        ),
        sa.CheckConstraint(
            "duration_ms BETWEEN 50 AND 2000",
            name="ck_job_duration",
        ),
    )

    op.create_index(
        "ix_jobs_status_created",
        "jobs",
        ["status", "created_at"],
    )

    op.create_table(
        "outbox",
        sa.Column(
            "id",
            sa.BigInteger(),
            sa.Identity(),
            primary_key=True,
        ),
        sa.Column(
            "job_id",
            sa.UUID(),
            sa.ForeignKey("jobs.id"),
            nullable=False,
        ),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
        ),
    )

    op.create_index(
        "ix_outbox_unpublished",
        "outbox",
        ["id"],
        postgresql_where=sa.text("published_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_table("outbox")
    op.drop_table("jobs")
