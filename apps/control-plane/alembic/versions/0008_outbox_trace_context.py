"""Preserve trace context through durable outbox publication."""

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE outbox ADD COLUMN trace_context jsonb "
        "CHECK (trace_context IS NULL OR (jsonb_typeof(trace_context)='object' "
        "AND octet_length(trace_context::text)<=1024))"
    )


def downgrade():
    op.execute("ALTER TABLE outbox DROP COLUMN trace_context")
