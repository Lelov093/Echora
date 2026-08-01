"""Preserve original Presence time separately from retry availability.

Revision ID: p4_b1_presence_retry_time
Revises: p4_b1_presence_runtime
"""

from alembic import op
import sqlalchemy as sa


revision = "p4_b1_presence_retry_time"
down_revision = "p4_b1_presence_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("presence_schedule_occurrences", sa.Column("next_attempt_at", sa.DateTime(timezone=True)))
    op.drop_index("idx_presence_occurrence_due", table_name="presence_schedule_occurrences")
    op.create_index(
        "idx_presence_occurrence_due",
        "presence_schedule_occurrences",
        ["status", "scheduled_for", "next_attempt_at", "lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_presence_occurrence_due", table_name="presence_schedule_occurrences")
    op.create_index(
        "idx_presence_occurrence_due",
        "presence_schedule_occurrences",
        ["status", "scheduled_for", "lease_expires_at"],
    )
    op.drop_column("presence_schedule_occurrences", "next_attempt_at")
