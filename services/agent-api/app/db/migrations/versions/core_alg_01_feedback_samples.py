"""Core algorithm feedback sample contract.

Revision ID: core_alg_01_feedback
Revises: p6_06_channel_trace
Create Date: 2026-06-05 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "core_alg_01_feedback"
down_revision: Union[str, Sequence[str], None] = "p6_06_channel_trace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("feedback_events", sa.Column("idempotency_key", sa.Text(), nullable=True))
    op.add_column(
        "feedback_events",
        sa.Column("feedback_source", sa.Text(), nullable=False, server_default=sa.text("'explicit'")),
    )
    op.add_column(
        "feedback_events",
        sa.Column("reward", sa.Double(), nullable=False, server_default=sa.text("0.0")),
    )
    op.add_column(
        "feedback_events",
        sa.Column(
            "sample_provenance",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("feedback_events", sa.Column("context_hash", sa.Text(), nullable=True))
    op.add_column("feedback_events", sa.Column("algorithm_key", sa.Text(), nullable=True))
    op.add_column(
        "feedback_events",
        sa.Column(
            "algorithm_version",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'core-feedback-v1'"),
        ),
    )
    op.add_column(
        "feedback_events",
        sa.Column("risk_level", sa.Text(), nullable=False, server_default=sa.text("'low'")),
    )
    op.add_column(
        "feedback_events",
        sa.Column(
            "redaction_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'not_required'"),
        ),
    )
    op.add_column(
        "feedback_events",
        sa.Column("training_eligible", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )

    op.drop_constraint("feedback_events_target_type_check", "feedback_events", type_="check")
    op.create_check_constraint(
        "feedback_events_target_type_check",
        "feedback_events",
        "target_type IN ("
        "'memory', 'memory_candidate', 'growth_candidate', 'growth_record', "
        "'presence_opportunity', 'related_memory', 'assistant_response', "
        "'retrieval_result', 'trace_run', 'conversation', 'continuity', "
        "'relationship', 'settings', 'strategy')",
    )
    op.drop_constraint("feedback_events_action_check", "feedback_events", type_="check")
    op.create_check_constraint(
        "feedback_events_action_check",
        "feedback_events",
        "action IN ("
        "'accept', 'edit_accept', 'reject', 'delete', 'lock', 'fade', "
        "'archive', 'reactivate', 'helpful', 'irrelevant', 'outdated', "
        "'wrong', 'confirm', 'revert', 'snooze', 'dismiss', "
        "'suppress_type', 'accept_presence', 'mark_important', "
        "'mark_sensitive', 'shown', 'continued', 'ignored', 'disabled', "
        "'useful', 'too_tool_like', 'too_verbose', 'too_intrusive')",
    )
    op.create_check_constraint(
        "ck_feedback_events_feedback_source",
        "feedback_events",
        "feedback_source IN ('explicit', 'inferred')",
    )
    op.create_check_constraint(
        "ck_feedback_events_reward",
        "feedback_events",
        "reward BETWEEN -1 AND 1",
    )
    op.create_check_constraint(
        "ck_feedback_events_risk_level",
        "feedback_events",
        "risk_level IN ('low', 'medium', 'high', 'critical')",
    )
    op.create_check_constraint(
        "ck_feedback_events_redaction_status",
        "feedback_events",
        "redaction_status IN ('not_required', 'redacted', 'blocked')",
    )
    op.create_index(
        "uq_feedback_events_idempotency_key",
        "feedback_events",
        ["idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL AND deleted_at IS NULL"),
    )
    op.create_index(
        "idx_feedback_events_training_pool",
        "feedback_events",
        ["companion_id", "training_eligible", "feedback_source", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_feedback_events_training_pool", table_name="feedback_events")
    op.drop_index("uq_feedback_events_idempotency_key", table_name="feedback_events")
    op.drop_constraint("ck_feedback_events_redaction_status", "feedback_events", type_="check")
    op.drop_constraint("ck_feedback_events_risk_level", "feedback_events", type_="check")
    op.drop_constraint("ck_feedback_events_reward", "feedback_events", type_="check")
    op.drop_constraint("ck_feedback_events_feedback_source", "feedback_events", type_="check")

    op.drop_constraint("feedback_events_action_check", "feedback_events", type_="check")
    op.execute(
        """
        UPDATE feedback_events
        SET action = CASE action
            WHEN 'shown' THEN 'confirm'
            WHEN 'continued' THEN 'confirm'
            WHEN 'ignored' THEN 'dismiss'
            WHEN 'disabled' THEN 'suppress_type'
            WHEN 'useful' THEN 'helpful'
            WHEN 'too_tool_like' THEN 'irrelevant'
            WHEN 'too_verbose' THEN 'irrelevant'
            WHEN 'too_intrusive' THEN 'dismiss'
            ELSE action
        END
        """
    )
    op.create_check_constraint(
        "feedback_events_action_check",
        "feedback_events",
        "action IN ("
        "'accept', 'edit_accept', 'reject', 'delete', 'lock', 'fade', "
        "'archive', 'reactivate', 'helpful', 'irrelevant', 'outdated', "
        "'wrong', 'confirm', 'revert', 'snooze', 'dismiss', "
        "'suppress_type', 'accept_presence', 'mark_important', 'mark_sensitive')",
    )
    op.drop_constraint("feedback_events_target_type_check", "feedback_events", type_="check")
    op.execute("UPDATE feedback_events SET target_type = 'assistant_response' WHERE target_type = 'strategy'")
    op.create_check_constraint(
        "feedback_events_target_type_check",
        "feedback_events",
        "target_type IN ("
        "'memory', 'memory_candidate', 'growth_candidate', 'growth_record', "
        "'presence_opportunity', 'related_memory', 'assistant_response', "
        "'retrieval_result', 'trace_run', 'conversation', 'continuity', "
        "'relationship', 'settings')",
    )

    for column in (
        "training_eligible",
        "redaction_status",
        "risk_level",
        "algorithm_version",
        "algorithm_key",
        "context_hash",
        "sample_provenance",
        "reward",
        "feedback_source",
        "idempotency_key",
    ):
        op.drop_column("feedback_events", column)
