"""phase2_04_continuity_userstate

Revision ID: p2_04_continuity
Revises: p2_03_review_abstraction
Create Date: 2026-05-30 00:00:00.000000

Create continuity_snapshots and user_state_snapshots tables.
Add continuity enhancement columns to conversations.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "p2_04_continuity"
down_revision: Union[str, Sequence[str], None] = "p2_03_review_abstraction"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Enum value lists ────────────────────────────────────────────────────

CONTINUITY_SNAPSHOT_TYPE_VALUES = (
    "conversation_end", "manual_refresh", "hub_refresh",
    "agent_run", "scheduled_maintenance", "user_requested",
)

MODE_KEY_VALUES = (
    "project", "creative", "daily", "learning",
    "game", "character", "voice", "virtual_world",
)

USER_STATE_SIGNAL_TYPE_VALUES = (
    "project_activity", "creative_activity", "presence_acceptance",
    "presence_dismissal", "memory_review_activity",
    "growth_review_activity", "continuity_need",
    "recent_confusion", "recent_satisfaction",
)


def upgrade() -> None:
    """Create continuity_snapshots, user_state_snapshots; enhance conversations."""

    # ── continuity_snapshots ────────────────────────────────────────────
    op.create_table(
        "continuity_snapshots",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("conversation_id", postgresql.UUID, nullable=True),
        sa.Column("trace_run_id", postgresql.UUID, nullable=True),
        sa.Column("snapshot_type", sa.Text(), server_default=sa.text("'agent_run'"), nullable=False),
        sa.Column("mode_key", sa.Text(), server_default=sa.text("'project'"), nullable=False),
        sa.Column("current_topic", sa.Text(), nullable=True),
        sa.Column("current_goal", sa.Text(), nullable=True),
        sa.Column("current_phase", sa.Text(), nullable=True),
        sa.Column("last_user_intent", sa.Text(), nullable=True),
        sa.Column("last_assistant_summary", sa.Text(), nullable=True),
        sa.Column("open_threads", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("unresolved_decisions", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("pending_reviews", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("suggested_next_steps", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("relevant_memory_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("relevant_growth_record_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("relevant_presence_opportunity_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("continuity_score", sa.Double(), server_default=sa.text("0.5"), nullable=False),
        sa.Column("freshness_score", sa.Double(), server_default=sa.text("0.5"), nullable=False),
        sa.Column("user_confirmed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("feedback_event_id", postgresql.UUID, nullable=True),
        sa.Column("snapshot_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["trace_run_id"], ["trace_runs.id"]),
        sa.ForeignKeyConstraint(["feedback_event_id"], ["feedback_events.id"]),
        sa.CheckConstraint(
            "snapshot_type IN ("
            "'conversation_end', 'manual_refresh', 'hub_refresh', "
            "'agent_run', 'scheduled_maintenance', 'user_requested')",
            name="continuity_snapshots_type_check",
        ),
        sa.CheckConstraint(
            "mode_key IN ("
            "'project', 'creative', 'daily', 'learning', "
            "'game', 'character', 'voice', 'virtual_world')",
            name="continuity_snapshots_mode_check",
        ),
        sa.CheckConstraint(
            "continuity_score BETWEEN 0 AND 1 AND freshness_score BETWEEN 0 AND 1",
            name="continuity_snapshots_score_check",
        ),
    )

    op.execute(
        "CREATE INDEX idx_continuity_snapshots_conversation_created "
        "ON continuity_snapshots(conversation_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_continuity_snapshots_user_companion_created "
        "ON continuity_snapshots(user_id, companion_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_continuity_snapshots_mode_created "
        "ON continuity_snapshots(mode_key, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_continuity_snapshots_relevant_memory_ids "
        "ON continuity_snapshots USING GIN(relevant_memory_ids)"
    )

    # ── user_state_snapshots ────────────────────────────────────────────
    op.create_table(
        "user_state_snapshots",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("conversation_id", postgresql.UUID, nullable=True),
        sa.Column("trace_run_id", postgresql.UUID, nullable=True),
        sa.Column("signal_type", sa.Text(), nullable=False),
        sa.Column("mode_key", sa.Text(), nullable=True),
        sa.Column("observed_value", sa.Double(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("previous_smoothed_value", sa.Double(), nullable=True),
        sa.Column("smoothed_value", sa.Double(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("smoothing_factor", sa.Double(), server_default=sa.text("0.8"), nullable=False),
        sa.Column("confidence", sa.Double(), server_default=sa.text("0.5"), nullable=False),
        sa.Column("source_event_count", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("observation_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("observation_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("source_feedback_event_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("source_trace_run_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("state_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["trace_run_id"], ["trace_runs.id"]),
        sa.CheckConstraint(
            "signal_type IN ("
            "'project_activity', 'creative_activity', 'presence_acceptance', "
            "'presence_dismissal', 'memory_review_activity', "
            "'growth_review_activity', 'continuity_need', "
            "'recent_confusion', 'recent_satisfaction')",
            name="user_state_snapshots_signal_type_check",
        ),
        sa.CheckConstraint(
            "mode_key IS NULL OR mode_key IN ("
            "'project', 'creative', 'daily', 'learning', "
            "'game', 'character', 'voice', 'virtual_world')",
            name="user_state_snapshots_mode_check",
        ),
        sa.CheckConstraint(
            "observed_value BETWEEN 0 AND 1 AND "
            "smoothed_value BETWEEN 0 AND 1 AND "
            "smoothing_factor BETWEEN 0 AND 1 AND "
            "confidence BETWEEN 0 AND 1",
            name="user_state_snapshots_score_check",
        ),
    )

    op.execute(
        "CREATE INDEX idx_user_state_snapshots_user_companion_signal_created "
        "ON user_state_snapshots(user_id, companion_id, signal_type, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_user_state_snapshots_mode_created "
        "ON user_state_snapshots(mode_key, created_at DESC)"
    )
    op.create_index("idx_user_state_snapshots_trace", "user_state_snapshots", ["trace_run_id"])

    # ── conversations: continuity enhancement columns ────────────────────
    op.add_column("conversations", sa.Column("continuity_updated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("conversations", sa.Column("latest_continuity_snapshot_id", postgresql.UUID, nullable=True))
    op.add_column("conversations", sa.Column("open_thread_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("conversations", sa.Column("pending_review_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("conversations", sa.Column("unresolved_decision_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("conversations", sa.Column("next_step_summary", sa.Text(), nullable=True))
    op.add_column("conversations", sa.Column("continuity_score", sa.Double(), server_default=sa.text("0.5"), nullable=False))

    op.create_foreign_key(
        "fk_conversations_latest_continuity_snapshot_id",
        "conversations", "continuity_snapshots",
        ["latest_continuity_snapshot_id"], ["id"],
    )
    op.execute(
        "ALTER TABLE conversations ADD CONSTRAINT conversations_continuity_score_check "
        "CHECK (continuity_score BETWEEN 0 AND 1)"
    )


def downgrade() -> None:
    """Drop continuity columns from conversations; drop user_state_snapshots and continuity_snapshots."""

    # Drop conversation enhancement columns
    op.execute("ALTER TABLE conversations DROP CONSTRAINT IF EXISTS conversations_continuity_score_check")
    op.drop_constraint("fk_conversations_latest_continuity_snapshot_id", "conversations", type_="foreignkey")
    op.drop_column("conversations", "continuity_score")
    op.drop_column("conversations", "next_step_summary")
    op.drop_column("conversations", "unresolved_decision_count")
    op.drop_column("conversations", "pending_review_count")
    op.drop_column("conversations", "open_thread_count")
    op.drop_column("conversations", "latest_continuity_snapshot_id")
    op.drop_column("conversations", "continuity_updated_at")

    # Drop user_state_snapshots
    op.drop_index("idx_user_state_snapshots_trace", table_name="user_state_snapshots")
    op.execute("DROP INDEX IF EXISTS idx_user_state_snapshots_mode_created")
    op.execute("DROP INDEX IF EXISTS idx_user_state_snapshots_user_companion_signal_created")
    op.drop_table("user_state_snapshots")

    # Drop continuity_snapshots
    op.execute("DROP INDEX IF EXISTS idx_continuity_snapshots_relevant_memory_ids")
    op.execute("DROP INDEX IF EXISTS idx_continuity_snapshots_mode_created")
    op.execute("DROP INDEX IF EXISTS idx_continuity_snapshots_user_companion_created")
    op.execute("DROP INDEX IF EXISTS idx_continuity_snapshots_conversation_created")
    op.drop_table("continuity_snapshots")
