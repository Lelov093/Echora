"""phase2_03_review_abstraction

Revision ID: p2_03_review_abstraction
Revises: p2_02_memory_timeline
Create Date: 2026-05-30 00:00:00.000000

Create review_batches and memory_abstraction_candidates tables.
Add review/abstraction enhancement columns to memory_candidates and memories.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "p2_03_review_abstraction"
down_revision: Union[str, Sequence[str], None] = "p2_02_memory_timeline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Enum value lists ────────────────────────────────────────────────────

REVIEW_BATCH_TYPE_VALUES = (
    "memory_candidates", "growth_candidates",
    "abstraction_candidates", "presence_opportunities",
    "mixed_review",
)

REVIEW_BATCH_STATUS_VALUES = ("open", "completed", "cancelled", "expired")

ABSTRACTION_TYPE_VALUES = (
    "stable_preference", "user_principle", "long_term_goal",
    "companion_strategy", "communication_style", "project_pattern",
    "creative_pattern", "boundary_rule", "self_narrative",
)

MEMORY_TYPE_VALUES = (
    "fact", "preference", "goal", "episodic", "correction",
    "relationship", "emotional", "self", "project", "creative", "system",
)

GROWTH_TYPE_VALUES = (
    "understanding_update", "communication_style", "companion_strategy",
    "boundary_update", "self_narrative", "mode_strategy",
)

ABSTRACTION_CANDIDATE_STATUS_VALUES = (
    "candidate", "accepted", "edited", "rejected", "merged",
    "expired", "committed_to_memory", "committed_to_growth",
)


def upgrade() -> None:
    """Create review_batches, memory_abstraction_candidates; enhance memory_candidates and memories."""

    # ── review_batches ──────────────────────────────────────────────────
    op.create_table(
        "review_batches",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("conversation_id", postgresql.UUID, nullable=True),
        sa.Column("batch_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("item_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("accepted_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("edited_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("rejected_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("skipped_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'open'"), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("item_refs", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.CheckConstraint(
            "batch_type IN ("
            "'memory_candidates', 'growth_candidates', "
            "'abstraction_candidates', 'presence_opportunities', "
            "'mixed_review')",
            name="review_batches_type_check",
        ),
        sa.CheckConstraint(
            "status IN ('open', 'completed', 'cancelled', 'expired')",
            name="review_batches_status_check",
        ),
        sa.CheckConstraint(
            "item_count >= 0 AND accepted_count >= 0 AND edited_count >= 0 AND "
            "rejected_count >= 0 AND skipped_count >= 0",
            name="review_batches_counts_check",
        ),
    )

    op.execute(
        "CREATE INDEX idx_review_batches_user_companion_status_created "
        "ON review_batches(user_id, companion_id, status, created_at DESC)"
    )
    op.create_index("idx_review_batches_type", "review_batches", ["batch_type"])

    # ── memory_abstraction_candidates ────────────────────────────────────
    op.create_table(
        "memory_abstraction_candidates",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("conversation_id", postgresql.UUID, nullable=True),
        sa.Column("trace_run_id", postgresql.UUID, nullable=True),
        sa.Column("source_memory_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("source_message_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("source_feedback_event_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("abstraction_type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("suggested_memory_type", sa.Text(), nullable=True),
        sa.Column("suggested_growth_type", sa.Text(), nullable=True),
        sa.Column("evidence_score", sa.Double(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("confidence", sa.Double(), server_default=sa.text("0.5"), nullable=False),
        sa.Column("recurrence", sa.Double(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("consistency_score", sa.Double(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("risk_score", sa.Double(), server_default=sa.text("0.0"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("impact_preview", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("cluster_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'candidate'"), nullable=False),
        sa.Column("accepted_memory_id", postgresql.UUID, nullable=True),
        sa.Column("accepted_growth_record_id", postgresql.UUID, nullable=True),
        sa.Column("edited_content", sa.Text(), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["trace_run_id"], ["trace_runs.id"]),
        sa.ForeignKeyConstraint(["accepted_memory_id"], ["memories.id"]),
        sa.ForeignKeyConstraint(["accepted_growth_record_id"], ["growth_records.id"]),
        sa.CheckConstraint(
            "abstraction_type IN ("
            "'stable_preference', 'user_principle', 'long_term_goal', "
            "'companion_strategy', 'communication_style', 'project_pattern', "
            "'creative_pattern', 'boundary_rule', 'self_narrative')",
            name="memory_abstraction_candidates_type_check",
        ),
        sa.CheckConstraint(
            "suggested_memory_type IS NULL OR suggested_memory_type IN ("
            "'fact', 'preference', 'goal', 'episodic', 'correction', "
            "'relationship', 'emotional', 'self', 'project', 'creative', 'system')",
            name="memory_abstraction_candidates_memory_type_check",
        ),
        sa.CheckConstraint(
            "suggested_growth_type IS NULL OR suggested_growth_type IN ("
            "'understanding_update', 'communication_style', 'companion_strategy', "
            "'boundary_update', 'self_narrative', 'mode_strategy')",
            name="memory_abstraction_candidates_growth_type_check",
        ),
        sa.CheckConstraint(
            "status IN ("
            "'candidate', 'accepted', 'edited', 'rejected', 'merged', "
            "'expired', 'committed_to_memory', 'committed_to_growth')",
            name="memory_abstraction_candidates_status_check",
        ),
        sa.CheckConstraint(
            "evidence_score BETWEEN 0 AND 1 AND "
            "confidence BETWEEN 0 AND 1 AND "
            "recurrence BETWEEN 0 AND 1 AND "
            "consistency_score BETWEEN 0 AND 1 AND "
            "risk_score BETWEEN 0 AND 1",
            name="memory_abstraction_candidates_score_check",
        ),
    )

    op.execute(
        "CREATE INDEX idx_memory_abstraction_candidates_user_companion_status "
        "ON memory_abstraction_candidates(user_id, companion_id, status, created_at DESC)"
    )
    op.create_index("idx_memory_abstraction_candidates_type", "memory_abstraction_candidates", ["abstraction_type"])
    op.create_index("idx_memory_abstraction_candidates_trace", "memory_abstraction_candidates", ["trace_run_id"])
    op.execute(
        "CREATE INDEX idx_memory_abstraction_candidates_source_memory_ids "
        "ON memory_abstraction_candidates USING GIN(source_memory_ids)"
    )

    # ── memory_candidates: review / abstraction columns ──────────────────
    op.add_column("memory_candidates", sa.Column("review_batch_id", postgresql.UUID, nullable=True))
    op.add_column("memory_candidates", sa.Column("review_priority", sa.Double(), server_default=sa.text("0.5"), nullable=False))
    op.add_column("memory_candidates", sa.Column("user_feedback_reason", sa.Text(), nullable=True))
    op.add_column("memory_candidates", sa.Column("abstraction_candidate_id", postgresql.UUID, nullable=True))
    op.add_column("memory_candidates", sa.Column("lifecycle_event_id", postgresql.UUID, nullable=True))
    op.add_column("memory_candidates", sa.Column("suggested_half_life_days", sa.Double(), nullable=True))
    op.add_column("memory_candidates", sa.Column("suggested_confidence_after_beta", sa.Double(), nullable=True))
    op.add_column("memory_candidates", sa.Column("calibration_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))

    op.create_foreign_key(
        "fk_memory_candidates_review_batch_id",
        "memory_candidates", "review_batches",
        ["review_batch_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_memory_candidates_abstraction_candidate_id",
        "memory_candidates", "memory_abstraction_candidates",
        ["abstraction_candidate_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_memory_candidates_lifecycle_event_id",
        "memory_candidates", "memory_lifecycle_events",
        ["lifecycle_event_id"], ["id"],
    )

    # ── memories: abstraction columns ────────────────────────────────────
    op.add_column("memories", sa.Column("abstraction_level", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("memories", sa.Column("source_abstraction_candidate_id", postgresql.UUID, nullable=True))
    op.add_column("memories", sa.Column("parent_memory_id", postgresql.UUID, nullable=True))

    op.execute(
        "ALTER TABLE memories ADD CONSTRAINT memories_abstraction_level_check "
        "CHECK (abstraction_level >= 0)"
    )
    op.create_foreign_key(
        "fk_memories_source_abstraction_candidate_id",
        "memories", "memory_abstraction_candidates",
        ["source_abstraction_candidate_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_memories_parent_memory_id",
        "memories", "memories",
        ["parent_memory_id"], ["id"],
    )

    op.create_index("idx_memories_abstraction_level", "memories", ["abstraction_level"])
    op.create_index("idx_memories_parent_memory_id", "memories", ["parent_memory_id"])


def downgrade() -> None:
    """Drop abstraction columns from memories and memory_candidates; drop new tables."""

    # Drop memory abstraction indexes and columns
    op.drop_index("idx_memories_parent_memory_id", table_name="memories")
    op.drop_index("idx_memories_abstraction_level", table_name="memories")
    op.drop_constraint("fk_memories_parent_memory_id", "memories", type_="foreignkey")
    op.drop_constraint("fk_memories_source_abstraction_candidate_id", "memories", type_="foreignkey")
    op.execute("ALTER TABLE memories DROP CONSTRAINT IF EXISTS memories_abstraction_level_check")
    op.drop_column("memories", "parent_memory_id")
    op.drop_column("memories", "source_abstraction_candidate_id")
    op.drop_column("memories", "abstraction_level")

    # Drop memory_candidates enhancement columns
    op.drop_constraint("fk_memory_candidates_lifecycle_event_id", "memory_candidates", type_="foreignkey")
    op.drop_constraint("fk_memory_candidates_abstraction_candidate_id", "memory_candidates", type_="foreignkey")
    op.drop_constraint("fk_memory_candidates_review_batch_id", "memory_candidates", type_="foreignkey")
    op.drop_column("memory_candidates", "calibration_json")
    op.drop_column("memory_candidates", "suggested_confidence_after_beta")
    op.drop_column("memory_candidates", "suggested_half_life_days")
    op.drop_column("memory_candidates", "lifecycle_event_id")
    op.drop_column("memory_candidates", "abstraction_candidate_id")
    op.drop_column("memory_candidates", "user_feedback_reason")
    op.drop_column("memory_candidates", "review_priority")
    op.drop_column("memory_candidates", "review_batch_id")

    # Drop memory_abstraction_candidates
    op.execute("DROP INDEX IF EXISTS idx_memory_abstraction_candidates_source_memory_ids")
    op.drop_index("idx_memory_abstraction_candidates_trace", table_name="memory_abstraction_candidates")
    op.drop_index("idx_memory_abstraction_candidates_type", table_name="memory_abstraction_candidates")
    op.execute("DROP INDEX IF EXISTS idx_memory_abstraction_candidates_user_companion_status")
    op.drop_table("memory_abstraction_candidates")

    # Drop review_batches
    op.drop_index("idx_review_batches_type", table_name="review_batches")
    op.execute("DROP INDEX IF EXISTS idx_review_batches_user_companion_status_created")
    op.drop_table("review_batches")
