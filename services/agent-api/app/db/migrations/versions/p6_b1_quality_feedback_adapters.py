"""Add generic durable sources and revisions to quality feedback.

Revision ID: p6_b1_quality_feedback_adapters
Revises: p6_b1_quality_feedback_runtime
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p6_b1_quality_feedback_adapters"
down_revision = "p6_b1_quality_feedback_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("evaluation_runs", sa.Column("source_domain", sa.Text(), nullable=True))
    op.add_column("evaluation_runs", sa.Column("source_entity_type", sa.Text(), nullable=True))
    op.add_column(
        "evaluation_runs",
        sa.Column("source_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("source_entity_revision", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "evaluation_runs",
        sa.Column("feedback_revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.execute(
        """
        UPDATE evaluation_runs
        SET source_domain = 'quality',
            source_entity_type = 'trace_run',
            source_entity_id = source_trace_run_id
        WHERE judge_type = 'deterministic_runtime_feedback'
          AND source_trace_run_id IS NOT NULL
        """
    )
    op.create_index(
        "uq_evaluation_run_runtime_feedback_source",
        "evaluation_runs",
        ["source_domain", "source_entity_type", "source_entity_id", "source_entity_revision"],
        unique=True,
        postgresql_where=sa.text(
            "judge_type = 'deterministic_runtime_feedback' "
            "AND deleted_at IS NULL AND source_entity_id IS NOT NULL"
        ),
    )
    op.create_check_constraint(
        "ck_evaluation_run_feedback_revisions",
        "evaluation_runs",
        "source_entity_revision >= 0 AND feedback_revision >= 1",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_evaluation_run_feedback_revisions", "evaluation_runs", type_="check"
    )
    op.drop_index(
        "uq_evaluation_run_runtime_feedback_source", table_name="evaluation_runs"
    )
    for column in (
        "feedback_revision",
        "source_entity_revision",
        "source_entity_id",
        "source_entity_type",
        "source_domain",
    ):
        op.drop_column("evaluation_runs", column)
