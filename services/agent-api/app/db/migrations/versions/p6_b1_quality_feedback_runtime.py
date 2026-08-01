"""Add durable runtime quality feedback orchestration to EvaluationRun.

Revision ID: p6_b1_quality_feedback_runtime
Revises: p5_b3_discord_room_runtime
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p6_b1_quality_feedback_runtime"
down_revision = "p5_b3_discord_room_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "evaluation_runs",
        sa.Column("source_trace_run_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("evaluation_runs", sa.Column("trigger_type", sa.Text(), nullable=True))
    op.add_column(
        "evaluation_runs",
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("evaluation_runs", sa.Column("lease_owner", sa.Text(), nullable=True))
    op.add_column(
        "evaluation_runs",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column(
            "error_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_foreign_key(
        "fk_evaluation_runs_source_trace",
        "evaluation_runs",
        "trace_runs",
        ["source_trace_run_id"],
        ["id"],
    )
    op.create_index(
        "uq_evaluation_run_runtime_feedback_trace",
        "evaluation_runs",
        ["source_trace_run_id"],
        unique=True,
        postgresql_where=sa.text(
            "judge_type = 'deterministic_runtime_feedback' AND deleted_at IS NULL"
        ),
    )
    op.create_index(
        "ix_evaluation_run_feedback_due",
        "evaluation_runs",
        ["judge_type", "status", "next_attempt_at", "lease_expires_at"],
    )
    op.create_check_constraint(
        "ck_evaluation_run_feedback_attempts",
        "evaluation_runs",
        "attempt_count >= 0 AND max_attempts >= 1 AND attempt_count <= max_attempts",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_evaluation_run_feedback_attempts", "evaluation_runs", type_="check"
    )
    op.drop_index("ix_evaluation_run_feedback_due", table_name="evaluation_runs")
    op.drop_index(
        "uq_evaluation_run_runtime_feedback_trace", table_name="evaluation_runs"
    )
    op.drop_constraint(
        "fk_evaluation_runs_source_trace", "evaluation_runs", type_="foreignkey"
    )
    for column in (
        "error_json",
        "lease_expires_at",
        "lease_owner",
        "next_attempt_at",
        "max_attempts",
        "attempt_count",
        "trigger_type",
        "source_trace_run_id",
    ):
        op.drop_column("evaluation_runs", column)
