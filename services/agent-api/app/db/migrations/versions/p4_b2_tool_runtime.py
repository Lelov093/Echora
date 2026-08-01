"""Add the durable P4-B2 lightweight Tool Runtime contract.

Revision ID: p4_b2_tool_runtime
Revises: p4_b1_presence_retry_time
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p4_b2_tool_runtime"
down_revision = "p4_b1_presence_retry_time"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tool_permissions", sa.Column("scope_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")))

    columns = (
        sa.Column("parent_tool_run_id", postgresql.UUID(as_uuid=True)),
        sa.Column("request_message_id", postgresql.UUID(as_uuid=True)),
        sa.Column("result_message_id", postgresql.UUID(as_uuid=True)),
        sa.Column("capability", sa.Text()),
        sa.Column("adapter_name", sa.Text()),
        sa.Column("adapter_version", sa.Text()),
        sa.Column("confirmation_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("confirmation_summary", sa.Text()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        sa.Column("confirmed_by", sa.Text()),
        sa.Column("idempotency_key", sa.Text()),
        sa.Column("input_schema_version", sa.Text()),
        sa.Column("output_schema_version", sa.Text()),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("lease_owner", sa.Text()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("cancel_requested_at", sa.DateTime(timezone=True)),
        sa.Column("terminal_reason", sa.Text()),
    )
    for column in columns:
        op.add_column("tool_runs", column)
    op.create_foreign_key("fk_tool_runs_parent", "tool_runs", "tool_runs", ["parent_tool_run_id"], ["id"])
    op.create_foreign_key("fk_tool_runs_request_message", "tool_runs", "messages", ["request_message_id"], ["id"])
    op.create_foreign_key("fk_tool_runs_result_message", "tool_runs", "messages", ["result_message_id"], ["id"])
    op.drop_constraint("tool_runs_status_check", "tool_runs", type_="check")
    op.execute("UPDATE tool_runs SET status = 'awaiting_confirmation', confirmation_required = true WHERE status = 'permission_required'")
    op.create_check_constraint(
        "tool_runs_status_check",
        "tool_runs",
        "status IN ('planned','awaiting_input','awaiting_confirmation','queued','running','retry_scheduled','succeeded','failed','cancelled','blocked','timed_out')",
    )
    op.create_check_constraint("ck_tool_runs_attempts", "tool_runs", "attempt_count >= 0 AND max_attempts BETWEEN 1 AND 10")
    op.create_check_constraint("ck_tool_runs_timeout", "tool_runs", "timeout_seconds BETWEEN 1 AND 120")
    op.create_index("idx_tool_runs_due", "tool_runs", ["status", "next_attempt_at", "lease_expires_at"])
    op.create_index(
        "uq_tool_runs_scope_idempotency",
        "tool_runs",
        ["user_id", "companion_id", "conversation_id", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL AND deleted_at IS NULL"),
    )

    op.create_table(
        "tool_resources",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companions.id"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id")),
        sa.Column("source_tool_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tool_runs.id")),
        sa.Column("resource_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text()),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("starts_at", sa.DateTime(timezone=True)),
        sa.Column("due_at", sa.DateTime(timezone=True)),
        sa.Column("timezone_name", sa.Text()),
        sa.Column("resource_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("resource_type IN ('reminder','calendar_event','note')", name="ck_tool_resources_type"),
        sa.CheckConstraint("status IN ('active','completed','cancelled','archived')", name="ck_tool_resources_status"),
    )
    op.create_index("idx_tool_resources_scope", "tool_resources", ["user_id", "companion_id", "resource_type", "status"])
    op.create_index("idx_tool_resources_due", "tool_resources", ["resource_type", "status", "due_at"])


def downgrade() -> None:
    op.drop_index("idx_tool_resources_due", table_name="tool_resources")
    op.drop_index("idx_tool_resources_scope", table_name="tool_resources")
    op.drop_table("tool_resources")
    op.drop_index("uq_tool_runs_scope_idempotency", table_name="tool_runs")
    op.drop_index("idx_tool_runs_due", table_name="tool_runs")
    op.drop_constraint("ck_tool_runs_timeout", "tool_runs", type_="check")
    op.drop_constraint("ck_tool_runs_attempts", "tool_runs", type_="check")
    op.drop_constraint("tool_runs_status_check", "tool_runs", type_="check")
    op.execute(
        """
        UPDATE tool_runs
        SET status = CASE
            WHEN status = 'awaiting_confirmation' THEN 'permission_required'
            WHEN status IN ('awaiting_input','queued','retry_scheduled') THEN 'planned'
            WHEN status = 'timed_out' THEN 'failed'
            ELSE status
        END
        """
    )
    op.create_check_constraint("tool_runs_status_check", "tool_runs", "status IN ('planned','permission_required','running','succeeded','failed','cancelled','blocked')")
    op.drop_constraint("fk_tool_runs_result_message", "tool_runs", type_="foreignkey")
    op.drop_constraint("fk_tool_runs_request_message", "tool_runs", type_="foreignkey")
    op.drop_constraint("fk_tool_runs_parent", "tool_runs", type_="foreignkey")
    for name in (
        "terminal_reason", "cancel_requested_at", "lease_expires_at", "lease_owner",
        "next_attempt_at", "timeout_seconds", "max_attempts", "attempt_count",
        "output_schema_version", "input_schema_version", "idempotency_key",
        "confirmed_by", "confirmed_at", "confirmation_summary", "confirmation_required",
        "adapter_version", "adapter_name", "capability", "result_message_id",
        "request_message_id", "parent_tool_run_id",
    ):
        op.drop_column("tool_runs", name)
    op.drop_column("tool_permissions", "scope_json")
