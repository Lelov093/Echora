"""Add an exclusive execution lease to Conversation TaskRuns.

Revision ID: conversation_task_run_lease_wb2
Revises: conversation_task_runtime_wb2
"""

from alembic import op
import sqlalchemy as sa


revision = "conversation_task_run_lease_wb2"
down_revision = "conversation_task_runtime_wb2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "conversation_task_runs",
        sa.Column("lease_owner", sa.String(120), nullable=True),
    )
    op.add_column(
        "conversation_task_runs",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_conversation_task_run_lease",
        "conversation_task_runs",
        ["status", "lease_expires_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_task_run_lease",
        table_name="conversation_task_runs",
    )
    op.drop_column("conversation_task_runs", "lease_expires_at")
    op.drop_column("conversation_task_runs", "lease_owner")
