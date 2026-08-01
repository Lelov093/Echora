"""phase2_01_feedback_base

Revision ID: p2_01_feedback
Revises: 9d0fd148cb7b
Create Date: 2026-05-30 00:00:00.000000

Create feedback_events table — the unified user-feedback record for
memory, growth, presence, retrieval, response, trace, continuity,
relationship, and settings targets.

Also adds source_feedback_event_id to bad_cases.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "p2_01_feedback"
down_revision: Union[str, Sequence[str], None] = "9d0fd148cb7b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Enum value lists ────────────────────────────────────────────────────

FEEDBACK_TARGET_TYPE_VALUES = (
    "memory", "memory_candidate", "growth_candidate", "growth_record",
    "presence_opportunity", "related_memory", "assistant_response",
    "retrieval_result", "trace_run", "conversation", "continuity",
    "relationship", "settings",
)

FEEDBACK_ACTION_VALUES = (
    "accept", "edit_accept", "reject", "delete", "lock", "fade",
    "archive", "reactivate", "helpful", "irrelevant", "outdated",
    "wrong", "confirm", "revert", "snooze", "dismiss",
    "suppress_type", "accept_presence", "mark_important",
    "mark_sensitive",
)

FEEDBACK_LABEL_VALUES = (
    "positive", "weak_positive", "neutral",
    "weak_negative", "negative", "strong_negative",
)

FEEDBACK_CALIBRATION_STATUS_VALUES = ("pending", "applied", "ignored", "failed")


def upgrade() -> None:
    """Create feedback_events table and add source_feedback_event_id to bad_cases."""

    # ── feedback_events ──────────────────────────────────────────────────
    op.create_table(
        "feedback_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("conversation_id", postgresql.UUID, nullable=True),
        sa.Column("message_id", postgresql.UUID, nullable=True),
        sa.Column("trace_run_id", postgresql.UUID, nullable=True),
        sa.Column("target_type", sa.Text(), nullable=False),
        sa.Column("target_id", postgresql.UUID, nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), server_default=sa.text("'neutral'"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("user_note", sa.Text(), nullable=True),
        sa.Column("score_delta", sa.Double(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("confidence_delta", sa.Double(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("strength_delta", sa.Double(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("priority_delta", sa.Double(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("applies_to_memory", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("applies_to_growth", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("applies_to_presence", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("applies_to_retrieval", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("applies_to_relationship", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("applies_to_boundary", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("calibration_status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("context_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["trace_run_id"], ["trace_runs.id"]),
        sa.CheckConstraint(
            "target_type IN ("
            "'memory', 'memory_candidate', 'growth_candidate', 'growth_record', "
            "'presence_opportunity', 'related_memory', 'assistant_response', "
            "'retrieval_result', 'trace_run', 'conversation', 'continuity', "
            "'relationship', 'settings')",
            name="feedback_events_target_type_check",
        ),
        sa.CheckConstraint(
            "action IN ("
            "'accept', 'edit_accept', 'reject', 'delete', 'lock', 'fade', "
            "'archive', 'reactivate', 'helpful', 'irrelevant', 'outdated', "
            "'wrong', 'confirm', 'revert', 'snooze', 'dismiss', "
            "'suppress_type', 'accept_presence', 'mark_important', "
            "'mark_sensitive')",
            name="feedback_events_action_check",
        ),
        sa.CheckConstraint(
            "label IN ("
            "'positive', 'weak_positive', 'neutral', "
            "'weak_negative', 'negative', 'strong_negative')",
            name="feedback_events_label_check",
        ),
        sa.CheckConstraint(
            "calibration_status IN ('pending', 'applied', 'ignored', 'failed')",
            name="feedback_events_calibration_status_check",
        ),
        sa.CheckConstraint(
            "score_delta BETWEEN -1 AND 1 AND "
            "confidence_delta BETWEEN -1 AND 1 AND "
            "strength_delta BETWEEN -1 AND 1 AND "
            "priority_delta BETWEEN -1 AND 1",
            name="feedback_events_score_delta_check",
        ),
    )

    # Indexes requiring DESC ordering use raw SQL
    op.execute(
        "CREATE INDEX idx_feedback_events_user_companion_created "
        "ON feedback_events(user_id, companion_id, created_at DESC)"
    )
    op.create_index("idx_feedback_events_target", "feedback_events", ["target_type", "target_id"])
    op.execute(
        "CREATE INDEX idx_feedback_events_conversation "
        "ON feedback_events(conversation_id, created_at DESC)"
    )
    op.create_index("idx_feedback_events_trace", "feedback_events", ["trace_run_id"])
    op.create_index("idx_feedback_events_calibration_status", "feedback_events", ["calibration_status"])
    op.create_index("idx_feedback_events_label", "feedback_events", ["label"])

    # ── bad_cases: source_feedback_event_id ──────────────────────────────
    op.add_column("bad_cases", sa.Column("source_feedback_event_id", postgresql.UUID, nullable=True))
    op.create_foreign_key(
        "fk_bad_cases_source_feedback_event_id",
        "bad_cases", "feedback_events",
        ["source_feedback_event_id"], ["id"],
    )


def downgrade() -> None:
    """Drop source_feedback_event_id from bad_cases and drop feedback_events table."""

    op.drop_constraint("fk_bad_cases_source_feedback_event_id", "bad_cases", type_="foreignkey")
    op.drop_column("bad_cases", "source_feedback_event_id")

    op.drop_index("idx_feedback_events_label", table_name="feedback_events")
    op.drop_index("idx_feedback_events_calibration_status", table_name="feedback_events")
    op.drop_index("idx_feedback_events_trace", table_name="feedback_events")
    op.drop_index("idx_feedback_events_target", table_name="feedback_events")
    op.execute("DROP INDEX IF EXISTS idx_feedback_events_conversation")
    op.execute("DROP INDEX IF EXISTS idx_feedback_events_user_companion_created")

    op.drop_table("feedback_events")
