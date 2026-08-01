"""phase2_02_memory_timeline_usage

Revision ID: p2_02_memory_timeline
Revises: p2_01_feedback
Create Date: 2026-05-30 00:00:00.000000

Create memory_usage_events and memory_lifecycle_events tables.
Add memory enhancement columns (timeline, feedback aggregation) to memories.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "p2_02_memory_timeline"
down_revision: Union[str, Sequence[str], None] = "p2_01_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Enum value lists ────────────────────────────────────────────────────

MEMORY_USAGE_EVENT_TYPE_VALUES = (
    "retrieved", "selected", "used_in_response", "used_in_growth",
    "used_in_presence", "used_in_relationship", "marked_helpful",
    "marked_irrelevant", "marked_wrong", "not_used_after_retrieval",
)

MEMORY_LIFECYCLE_EVENT_TYPE_VALUES = (
    "created", "candidate_accepted", "candidate_edited",
    "candidate_merged", "reactivated", "strengthened", "weakened",
    "faded", "locked", "archived", "suppressed", "deleted",
    "confidence_updated", "half_life_updated", "abstraction_created",
    "abstraction_committed", "conflict_flagged", "outdated_flagged",
)

MEMORY_STATE_VALUES = ("active", "dormant", "archived", "suppressed", "deleted")

FEEDBACK_LABEL_VALUES = (
    "positive", "weak_positive", "neutral",
    "weak_negative", "negative", "strong_negative",
)


def upgrade() -> None:
    """Create memory_usage_events, memory_lifecycle_events; enhance memories."""

    # ── memory_usage_events ─────────────────────────────────────────────
    op.create_table(
        "memory_usage_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("conversation_id", postgresql.UUID, nullable=True),
        sa.Column("message_id", postgresql.UUID, nullable=True),
        sa.Column("trace_run_id", postgresql.UUID, nullable=True),
        sa.Column("trace_step_id", postgresql.UUID, nullable=True),
        sa.Column("memory_id", postgresql.UUID, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("semantic_similarity", sa.Double(), nullable=True),
        sa.Column("retrieval_score", sa.Double(), nullable=True),
        sa.Column("memory_strength_snapshot", sa.Double(), nullable=True),
        sa.Column("confidence_snapshot", sa.Double(), nullable=True),
        sa.Column("goal_relevance_snapshot", sa.Double(), nullable=True),
        sa.Column("relationship_impact_snapshot", sa.Double(), nullable=True),
        sa.Column("rank_before_rerank", sa.Integer(), nullable=True),
        sa.Column("rank_after_rerank", sa.Integer(), nullable=True),
        sa.Column("selected_for_context", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("used_in_response", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("used_in_growth", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("used_in_presence", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("used_in_relationship", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("why_selected", sa.Text(), nullable=True),
        sa.Column("why_excluded", sa.Text(), nullable=True),
        sa.Column("feedback_event_id", postgresql.UUID, nullable=True),
        sa.Column("feedback_label", sa.Text(), nullable=True),
        sa.Column("score_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("usage_context", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["trace_run_id"], ["trace_runs.id"]),
        sa.ForeignKeyConstraint(["trace_step_id"], ["trace_steps.id"]),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"]),
        sa.ForeignKeyConstraint(["feedback_event_id"], ["feedback_events.id"]),
        sa.CheckConstraint(
            "event_type IN ("
            "'retrieved', 'selected', 'used_in_response', 'used_in_growth', "
            "'used_in_presence', 'used_in_relationship', 'marked_helpful', "
            "'marked_irrelevant', 'marked_wrong', 'not_used_after_retrieval')",
            name="memory_usage_events_type_check",
        ),
        sa.CheckConstraint(
            "feedback_label IS NULL OR feedback_label IN ("
            "'positive', 'weak_positive', 'neutral', "
            "'weak_negative', 'negative', 'strong_negative')",
            name="memory_usage_events_feedback_label_check",
        ),
        sa.CheckConstraint(
            "(semantic_similarity IS NULL OR semantic_similarity BETWEEN 0 AND 1) AND "
            "(retrieval_score IS NULL OR retrieval_score BETWEEN 0 AND 1) AND "
            "(memory_strength_snapshot IS NULL OR memory_strength_snapshot BETWEEN 0 AND 1) AND "
            "(confidence_snapshot IS NULL OR confidence_snapshot BETWEEN 0 AND 1)",
            name="memory_usage_events_score_check",
        ),
    )

    op.execute(
        "CREATE INDEX idx_memory_usage_events_memory_created "
        "ON memory_usage_events(memory_id, created_at DESC)"
    )
    op.create_index("idx_memory_usage_events_trace", "memory_usage_events", ["trace_run_id"])
    op.execute(
        "CREATE INDEX idx_memory_usage_events_conversation "
        "ON memory_usage_events(conversation_id, created_at DESC)"
    )
    op.create_index("idx_memory_usage_events_type", "memory_usage_events", ["event_type"])
    op.create_index("idx_memory_usage_events_feedback", "memory_usage_events", ["feedback_label"])

    # ── memory_lifecycle_events ─────────────────────────────────────────
    op.create_table(
        "memory_lifecycle_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("conversation_id", postgresql.UUID, nullable=True),
        sa.Column("message_id", postgresql.UUID, nullable=True),
        sa.Column("trace_run_id", postgresql.UUID, nullable=True),
        sa.Column("memory_id", postgresql.UUID, nullable=False),
        sa.Column("source_candidate_id", postgresql.UUID, nullable=True),
        sa.Column("feedback_event_id", postgresql.UUID, nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("previous_state", sa.Text(), nullable=True),
        sa.Column("new_state", sa.Text(), nullable=True),
        sa.Column("previous_strength", sa.Double(), nullable=True),
        sa.Column("new_strength", sa.Double(), nullable=True),
        sa.Column("strength_delta", sa.Double(), nullable=True),
        sa.Column("previous_confidence", sa.Double(), nullable=True),
        sa.Column("new_confidence", sa.Double(), nullable=True),
        sa.Column("confidence_delta", sa.Double(), nullable=True),
        sa.Column("previous_half_life_days", sa.Double(), nullable=True),
        sa.Column("new_half_life_days", sa.Double(), nullable=True),
        sa.Column("score_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("before_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("after_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["trace_run_id"], ["trace_runs.id"]),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"]),
        sa.ForeignKeyConstraint(["source_candidate_id"], ["memory_candidates.id"]),
        sa.ForeignKeyConstraint(["feedback_event_id"], ["feedback_events.id"]),
        sa.CheckConstraint(
            "event_type IN ("
            "'created', 'candidate_accepted', 'candidate_edited', "
            "'candidate_merged', 'reactivated', 'strengthened', 'weakened', "
            "'faded', 'locked', 'archived', 'suppressed', 'deleted', "
            "'confidence_updated', 'half_life_updated', 'abstraction_created', "
            "'abstraction_committed', 'conflict_flagged', 'outdated_flagged')",
            name="memory_lifecycle_events_type_check",
        ),
        sa.CheckConstraint(
            "previous_state IS NULL OR previous_state IN "
            "('active', 'dormant', 'archived', 'suppressed', 'deleted')",
            name="memory_lifecycle_events_state_check",
        ),
        sa.CheckConstraint(
            "new_state IS NULL OR new_state IN "
            "('active', 'dormant', 'archived', 'suppressed', 'deleted')",
            name="memory_lifecycle_events_new_state_check",
        ),
    )

    op.execute(
        "CREATE INDEX idx_memory_lifecycle_events_memory_created "
        "ON memory_lifecycle_events(memory_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_memory_lifecycle_events_user_companion_created "
        "ON memory_lifecycle_events(user_id, companion_id, created_at DESC)"
    )
    op.create_index("idx_memory_lifecycle_events_type", "memory_lifecycle_events", ["event_type"])
    op.create_index("idx_memory_lifecycle_events_trace", "memory_lifecycle_events", ["trace_run_id"])

    # ── memories: timeline / feedback aggregation columns ────────────────
    op.add_column("memories", sa.Column("last_feedback_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("memories", sa.Column("last_used_in_response_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("memories", sa.Column("last_used_in_growth_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("memories", sa.Column("last_used_in_presence_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("memories", sa.Column("feedback_score", sa.Double(), server_default=sa.text("0.0"), nullable=False))
    op.add_column("memories", sa.Column("helpful_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("memories", sa.Column("irrelevant_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("memories", sa.Column("outdated_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("memories", sa.Column("wrong_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("memories", sa.Column("impact_summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("memories", sa.Column("lifecycle_summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))

    # CHECK: feedback_score BETWEEN -1 AND 1
    op.execute(
        "ALTER TABLE memories ADD CONSTRAINT memories_feedback_score_check "
        "CHECK (feedback_score BETWEEN -1 AND 1)"
    )

    # Indexes on new memory columns
    op.execute("CREATE INDEX idx_memories_feedback_score ON memories(feedback_score DESC)")
    op.execute("CREATE INDEX idx_memories_last_feedback_at ON memories(last_feedback_at DESC)")


def downgrade() -> None:
    """Drop memory enhancement columns; drop memory_lifecycle_events and memory_usage_events."""

    # Drop memory indexes and columns
    op.execute("DROP INDEX IF EXISTS idx_memories_last_feedback_at")
    op.execute("DROP INDEX IF EXISTS idx_memories_feedback_score")
    op.execute("ALTER TABLE memories DROP CONSTRAINT IF EXISTS memories_feedback_score_check")

    op.drop_column("memories", "lifecycle_summary")
    op.drop_column("memories", "impact_summary")
    op.drop_column("memories", "wrong_count")
    op.drop_column("memories", "outdated_count")
    op.drop_column("memories", "irrelevant_count")
    op.drop_column("memories", "helpful_count")
    op.drop_column("memories", "feedback_score")
    op.drop_column("memories", "last_used_in_presence_at")
    op.drop_column("memories", "last_used_in_growth_at")
    op.drop_column("memories", "last_used_in_response_at")
    op.drop_column("memories", "last_feedback_at")

    # Drop memory_lifecycle_events
    op.drop_index("idx_memory_lifecycle_events_trace", table_name="memory_lifecycle_events")
    op.drop_index("idx_memory_lifecycle_events_type", table_name="memory_lifecycle_events")
    op.execute("DROP INDEX IF EXISTS idx_memory_lifecycle_events_user_companion_created")
    op.execute("DROP INDEX IF EXISTS idx_memory_lifecycle_events_memory_created")
    op.drop_table("memory_lifecycle_events")

    # Drop memory_usage_events
    op.drop_index("idx_memory_usage_events_feedback", table_name="memory_usage_events")
    op.drop_index("idx_memory_usage_events_type", table_name="memory_usage_events")
    op.execute("DROP INDEX IF EXISTS idx_memory_usage_events_conversation")
    op.drop_index("idx_memory_usage_events_trace", table_name="memory_usage_events")
    op.execute("DROP INDEX IF EXISTS idx_memory_usage_events_memory_created")
    op.drop_table("memory_usage_events")
