"""Add durable Companion deletion requests and resumable purge scope.

Revision ID: data_rights_deletion_v1
Revises: conversation_task_run_lease_wb2
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "data_rights_deletion_v1"
down_revision = "conversation_task_run_lease_wb2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companion_deletion_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("companion_scope_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="trash", nullable=False),
        sa.Column("deletion_mode", sa.String(length=24), nullable=False),
        sa.Column("previous_companion_status", sa.String(length=50), nullable=True),
        sa.Column("current_stage", sa.String(length=80), server_default="recovery_window", nullable=False),
        sa.Column("restore_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("affected_counts_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("deleted_counts_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("failure_code", sa.String(length=120), nullable=True),
        sa.Column("failure_stage", sa.String(length=120), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purge_after", sa.DateTime(timezone=True), nullable=False),
        sa.Column("purge_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("backup_delete_due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.CheckConstraint(
            "status IN ('trash','purging','completed','restored','failed')",
            name="ck_companion_deletion_status",
        ),
        sa.CheckConstraint(
            "deletion_mode IN ('recovery_window','immediate')",
            name="ck_companion_deletion_mode",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "idempotency_key", name="uq_companion_deletion_idempotency"),
    )
    op.create_index(
        "ix_companion_deletion_due",
        "companion_deletion_requests",
        ["status", "purge_after"],
    )
    op.create_index(
        "ix_companion_deletion_companion",
        "companion_deletion_requests",
        ["companion_id", "status"],
    )

    op.create_table(
        "companion_deletion_scope_rows",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("deletion_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("table_name", sa.Text(), nullable=False),
        sa.Column("row_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["deletion_request_id"],
            ["companion_deletion_requests.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "deletion_request_id",
            "table_name",
            "row_id",
            name="uq_companion_deletion_scope_row",
        ),
    )
    op.create_index(
        "ix_companion_deletion_scope_lookup",
        "companion_deletion_scope_rows",
        ["deletion_request_id", "table_name"],
    )


def downgrade() -> None:
    op.drop_index("ix_companion_deletion_scope_lookup", table_name="companion_deletion_scope_rows")
    op.drop_table("companion_deletion_scope_rows")
    op.drop_index("ix_companion_deletion_companion", table_name="companion_deletion_requests")
    op.drop_index("ix_companion_deletion_due", table_name="companion_deletion_requests")
    op.drop_table("companion_deletion_requests")
