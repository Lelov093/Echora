"""Add durable bounded Conversation Task runtime.

Revision ID: conversation_task_runtime_wb2
Revises: p6_b1_quality_feedback_adapters
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "conversation_task_runtime_wb2"
down_revision = "p6_b1_quality_feedback_adapters"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_task_runs",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companions.id"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("source_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("trace_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trace_runs.id"), nullable=True),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("acceptance_state", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("plan_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_step_order", sa.Integer(), nullable=True),
        sa.Column("max_steps", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("max_replans", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("replan_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_tool_runs", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("tool_run_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_tokens", sa.Integer(), nullable=False, server_default="12000"),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("idempotency_key", sa.String(240), nullable=False),
        sa.Column("stop_reason", sa.Text(), nullable=True),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.CheckConstraint("status IN ('draft','awaiting_input','awaiting_approval','ready','running','paused','blocked','completed','cancelled','failed')", name="ck_conversation_task_run_status"),
        sa.CheckConstraint("acceptance_state IN ('pending','verified','rejected','not_applicable')", name="ck_conversation_task_acceptance"),
        sa.CheckConstraint("max_steps BETWEEN 1 AND 6 AND max_replans BETWEEN 0 AND 2 AND max_tool_runs BETWEEN 0 AND 6", name="ck_conversation_task_budgets"),
        sa.CheckConstraint("plan_version >= 1 AND revision >= 1 AND replan_count >= 0 AND tool_run_count >= 0 AND token_count >= 0", name="ck_conversation_task_counters"),
        sa.UniqueConstraint("user_id", "companion_id", "conversation_id", "idempotency_key", name="uq_conversation_task_scope_idempotency"),
    )
    op.create_index("ix_conversation_task_active", "conversation_task_runs", ["conversation_id", "companion_id", "status"])

    op.create_table(
        "conversation_task_steps",
        sa.Column("task_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversation_task_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("executor_type", sa.String(32), nullable=False),
        sa.Column("capability", sa.String(64), nullable=True),
        sa.Column("risk_level", sa.String(16), nullable=False, server_default="low"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("dependencies_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("input_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("output_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("acceptance_criteria_json", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("evidence_refs", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("confirmation_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=False, server_default="60"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.CheckConstraint("executor_type IN ('tool','research','verify')", name="ck_conversation_task_step_executor"),
        sa.CheckConstraint("risk_level IN ('low','medium','high','critical')", name="ck_conversation_task_step_risk"),
        sa.CheckConstraint("status IN ('pending','ready','running','awaiting_input','awaiting_approval','succeeded','failed','blocked','cancelled','skipped')", name="ck_conversation_task_step_status"),
        sa.CheckConstraint("attempt_count >= 0 AND max_attempts BETWEEN 1 AND 3 AND timeout_seconds BETWEEN 1 AND 300", name="ck_conversation_task_step_budget"),
        sa.UniqueConstraint("task_run_id", "step_order", name="uq_conversation_task_step_order"),
    )
    op.create_index("ix_conversation_task_step_ready", "conversation_task_steps", ["task_run_id", "status", "step_order"])

    op.create_table(
        "conversation_task_step_attempts",
        sa.Column("task_step_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversation_task_steps.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("executor_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("tool_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tool_runs.id"), nullable=True),
        sa.Column("trace_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trace_runs.id"), nullable=True),
        sa.Column("provider_name", sa.String(80), nullable=True),
        sa.Column("model_name", sa.String(160), nullable=True),
        sa.Column("input_summary", sa.Text(), nullable=True),
        sa.Column("observation_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("verification_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("error_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("token_usage_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("lease_owner", sa.String(100), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("elapsed_ms", sa.Integer(), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.CheckConstraint("executor_type IN ('tool','research','verify')", name="ck_conversation_task_attempt_executor"),
        sa.CheckConstraint("status IN ('queued','running','awaiting_approval','succeeded','failed','cancelled','timed_out')", name="ck_conversation_task_attempt_status"),
        sa.CheckConstraint("attempt_number BETWEEN 1 AND 3", name="ck_conversation_task_attempt_number"),
        sa.UniqueConstraint("task_step_id", "attempt_number", name="uq_conversation_task_attempt_number"),
    )
    op.create_index("ix_conversation_task_attempt_lease", "conversation_task_step_attempts", ["status", "lease_expires_at"])

    op.create_table(
        "conversation_task_plan_revisions",
        sa.Column("task_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversation_task_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("previous_version", sa.Integer(), nullable=True),
        sa.Column("trigger", sa.String(64), nullable=False),
        sa.Column("goal", sa.Text(), nullable=False),
        sa.Column("plan_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("changes_json", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column("approval_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_by", sa.String(32), nullable=False, server_default="planner"),
        sa.Column("source_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.CheckConstraint("version >= 1 AND (previous_version IS NULL OR previous_version < version)", name="ck_conversation_task_plan_version"),
        sa.UniqueConstraint("task_run_id", "version", name="uq_conversation_task_plan_version"),
    )


def downgrade() -> None:
    op.drop_table("conversation_task_plan_revisions")
    op.drop_index("ix_conversation_task_attempt_lease", table_name="conversation_task_step_attempts")
    op.drop_table("conversation_task_step_attempts")
    op.drop_index("ix_conversation_task_step_ready", table_name="conversation_task_steps")
    op.drop_table("conversation_task_steps")
    op.drop_index("ix_conversation_task_active", table_name="conversation_task_runs")
    op.drop_table("conversation_task_runs")
