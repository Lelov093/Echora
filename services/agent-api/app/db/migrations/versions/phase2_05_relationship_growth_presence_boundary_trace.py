"""phase2_05_relationship_growth_presence_boundary_trace

Revision ID: p2_05_relationship
Revises: p2_04_continuity
Create Date: 2026-05-30 00:00:00.000000

Create relationship_explanation_events table.
Add enhancement columns to growth_candidates, growth_records,
presence_opportunities, relationship_states, boundary_settings,
trace_steps, and bad_cases.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "p2_05_relationship"
down_revision: Union[str, Sequence[str], None] = "p2_04_continuity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Enum value lists ────────────────────────────────────────────────────

RELATIONSHIP_DIMENSION_VALUES = (
    "familiarity", "understanding", "collaboration",
    "trust", "emotional_closeness", "boundary_awareness",
    "continuity",
)

FEEDBACK_LABEL_VALUES = (
    "positive", "weak_positive", "neutral",
    "weak_negative", "negative", "strong_negative",
)


def upgrade() -> None:
    """Create relationship_explanation_events; enhance growth, presence, relationship, boundary, trace, bad_cases."""

    # ── relationship_explanation_events ─────────────────────────────────
    op.create_table(
        "relationship_explanation_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("conversation_id", postgresql.UUID, nullable=True),
        sa.Column("trace_run_id", postgresql.UUID, nullable=True),
        sa.Column("relationship_event_id", postgresql.UUID, nullable=True),
        sa.Column("feedback_event_id", postgresql.UUID, nullable=True),
        sa.Column("dimension", sa.Text(), nullable=False),
        sa.Column("previous_value", sa.Double(), nullable=True),
        sa.Column("new_value", sa.Double(), nullable=True),
        sa.Column("delta", sa.Double(), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("evidence_memory_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("evidence_message_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("evidence_growth_record_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("confidence", sa.Double(), server_default=sa.text("0.5"), nullable=False),
        sa.Column("user_visible", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("user_confirmed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("score_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("impact_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["trace_run_id"], ["trace_runs.id"]),
        sa.ForeignKeyConstraint(["relationship_event_id"], ["relationship_events.id"]),
        sa.ForeignKeyConstraint(["feedback_event_id"], ["feedback_events.id"]),
        sa.CheckConstraint(
            "dimension IN ("
            "'familiarity', 'understanding', 'collaboration', "
            "'trust', 'emotional_closeness', 'boundary_awareness', "
            "'continuity')",
            name="relationship_explanation_dimension_check",
        ),
        sa.CheckConstraint(
            "(previous_value IS NULL OR previous_value BETWEEN 0 AND 1) AND "
            "(new_value IS NULL OR new_value BETWEEN 0 AND 1) AND "
            "(delta IS NULL OR delta BETWEEN -1 AND 1) AND "
            "confidence BETWEEN 0 AND 1",
            name="relationship_explanation_score_check",
        ),
    )

    op.execute(
        "CREATE INDEX idx_relationship_explanation_events_user_companion_created "
        "ON relationship_explanation_events(user_id, companion_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX idx_relationship_explanation_events_dimension "
        "ON relationship_explanation_events(dimension, created_at DESC)"
    )
    op.create_index("idx_relationship_explanation_events_trace", "relationship_explanation_events", ["trace_run_id"])
    op.execute(
        "CREATE INDEX idx_relationship_explanation_events_evidence_memory_ids "
        "ON relationship_explanation_events USING GIN(evidence_memory_ids)"
    )

    # ── growth_candidates: review / feedback / abstraction columns ───────
    op.add_column("growth_candidates", sa.Column("review_batch_id", postgresql.UUID, nullable=True))
    op.add_column("growth_candidates", sa.Column("source_abstraction_candidate_id", postgresql.UUID, nullable=True))
    op.add_column("growth_candidates", sa.Column("feedback_score", sa.Double(), server_default=sa.text("0.0"), nullable=False))
    op.add_column("growth_candidates", sa.Column("positive_feedback_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("growth_candidates", sa.Column("negative_feedback_count", sa.Integer(), server_default=sa.text("0"), nullable=False))
    op.add_column("growth_candidates", sa.Column("impact_preview_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("growth_candidates", sa.Column("profile_patch_preview", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("growth_candidates", sa.Column("user_feedback_reason", sa.Text(), nullable=True))
    op.add_column("growth_candidates", sa.Column("calibration_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))

    op.create_foreign_key(
        "fk_growth_candidates_review_batch_id",
        "growth_candidates", "review_batches",
        ["review_batch_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_growth_candidates_source_abstraction_candidate_id",
        "growth_candidates", "memory_abstraction_candidates",
        ["source_abstraction_candidate_id"], ["id"],
    )
    op.execute(
        "ALTER TABLE growth_candidates ADD CONSTRAINT growth_candidates_feedback_score_check "
        "CHECK (feedback_score BETWEEN -1 AND 1)"
    )

    # ── growth_records: abstraction / profile / downstream columns ──────
    op.add_column("growth_records", sa.Column("source_abstraction_candidate_id", postgresql.UUID, nullable=True))
    op.add_column("growth_records", sa.Column("profile_patch_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("growth_records", sa.Column("profile_version_before", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("growth_records", sa.Column("profile_version_after", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("growth_records", sa.Column("downstream_trace_run_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False))
    op.add_column("growth_records", sa.Column("downstream_memory_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False))
    op.add_column("growth_records", sa.Column("downstream_presence_opportunity_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False))
    op.add_column("growth_records", sa.Column("feedback_score", sa.Double(), server_default=sa.text("0.0"), nullable=False))
    op.add_column("growth_records", sa.Column("last_feedback_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("growth_records", sa.Column("revert_impact_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))

    op.create_foreign_key(
        "fk_growth_records_source_abstraction_candidate_id",
        "growth_records", "memory_abstraction_candidates",
        ["source_abstraction_candidate_id"], ["id"],
    )

    # ── presence_opportunities: feedback / timing / calibration columns ──
    # Note: snoozed_until already exists from Phase 1
    op.add_column("presence_opportunities", sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("presence_opportunities", sa.Column("dismissed_reason", sa.Text(), nullable=True))
    op.add_column("presence_opportunities", sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("presence_opportunities", sa.Column("suppress_type_rule_applied", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.add_column("presence_opportunities", sa.Column("feedback_event_id", postgresql.UUID, nullable=True))
    op.add_column("presence_opportunities", sa.Column("feedback_label", sa.Text(), nullable=True))
    op.add_column("presence_opportunities", sa.Column("timing_score", sa.Double(), server_default=sa.text("0.5"), nullable=False))
    op.add_column("presence_opportunities", sa.Column("type_affinity_snapshot", sa.Double(), server_default=sa.text("0.5"), nullable=False))
    op.add_column("presence_opportunities", sa.Column("opportunity_context_hash", sa.Text(), nullable=True))
    op.add_column("presence_opportunities", sa.Column("meaningful_silence_reason", sa.Text(), nullable=True))
    op.add_column("presence_opportunities", sa.Column("calibration_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))

    op.create_foreign_key(
        "fk_presence_opportunities_feedback_event_id",
        "presence_opportunities", "feedback_events",
        ["feedback_event_id"], ["id"],
    )
    op.execute(
        "ALTER TABLE presence_opportunities ADD CONSTRAINT presence_opportunities_feedback_label_check "
        "CHECK (feedback_label IS NULL OR feedback_label IN ("
        "'positive', 'weak_positive', 'neutral', "
        "'weak_negative', 'negative', 'strong_negative'))"
    )
    op.execute(
        "ALTER TABLE presence_opportunities ADD CONSTRAINT presence_opportunities_timing_score_check "
        "CHECK (timing_score BETWEEN 0 AND 1 AND type_affinity_snapshot BETWEEN 0 AND 1)"
    )

    # ── relationship_states: trend / explanation columns ─────────────────
    op.add_column("relationship_states", sa.Column("familiarity_trend", sa.Double(), server_default=sa.text("0.0"), nullable=False))
    op.add_column("relationship_states", sa.Column("understanding_trend", sa.Double(), server_default=sa.text("0.0"), nullable=False))
    op.add_column("relationship_states", sa.Column("collaboration_trend", sa.Double(), server_default=sa.text("0.0"), nullable=False))
    op.add_column("relationship_states", sa.Column("trust_trend", sa.Double(), server_default=sa.text("0.0"), nullable=False))
    op.add_column("relationship_states", sa.Column("emotional_closeness_trend", sa.Double(), server_default=sa.text("0.0"), nullable=False))
    op.add_column("relationship_states", sa.Column("boundary_awareness_trend", sa.Double(), server_default=sa.text("0.0"), nullable=False))
    op.add_column("relationship_states", sa.Column("continuity_trend", sa.Double(), server_default=sa.text("0.0"), nullable=False))
    op.add_column("relationship_states", sa.Column("last_explanation_event_id", postgresql.UUID, nullable=True))
    op.add_column("relationship_states", sa.Column("explanation_summary", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("relationship_states", sa.Column("last_changed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_foreign_key(
        "fk_relationship_states_last_explanation_event_id",
        "relationship_states", "relationship_explanation_events",
        ["last_explanation_event_id"], ["id"],
    )
    op.execute(
        "ALTER TABLE relationship_states ADD CONSTRAINT relationship_states_trend_check "
        "CHECK ("
        "familiarity_trend BETWEEN -1 AND 1 AND "
        "understanding_trend BETWEEN -1 AND 1 AND "
        "collaboration_trend BETWEEN -1 AND 1 AND "
        "trust_trend BETWEEN -1 AND 1 AND "
        "emotional_closeness_trend BETWEEN -1 AND 1 AND "
        "boundary_awareness_trend BETWEEN -1 AND 1 AND "
        "continuity_trend BETWEEN -1 AND 1"
        ")"
    )

    # ── boundary_settings: policy / quiet-hours / presence-control columns
    # Note: suppressed_presence_types (TEXT[]) already exists from Phase 1
    # Phase 2 adds suppressed_presence_rules (JSONB) alongside it
    op.add_column("boundary_settings", sa.Column("quiet_hours", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("boundary_settings", sa.Column("suppressed_presence_rules", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False))
    op.add_column("boundary_settings", sa.Column("memory_confirmation_policy", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("boundary_settings", sa.Column("growth_confirmation_policy", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("boundary_settings", sa.Column("feedback_usage_policy", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("boundary_settings", sa.Column("continuity_visibility_policy", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("boundary_settings", sa.Column("max_presence_per_day", sa.Integer(), nullable=True))
    op.add_column("boundary_settings", sa.Column("min_presence_interval_minutes", sa.Integer(), nullable=True))
    op.add_column("boundary_settings", sa.Column("meaningful_silence_enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False))

    # ── trace_steps: calibration / impact columns ────────────────────────
    op.add_column("trace_steps", sa.Column("calibration_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("trace_steps", sa.Column("feedback_event_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False))
    op.add_column("trace_steps", sa.Column("memory_usage_event_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False))
    op.add_column("trace_steps", sa.Column("lifecycle_event_ids", postgresql.ARRAY(postgresql.UUID), server_default=sa.text("'{}'"), nullable=False))
    op.add_column("trace_steps", sa.Column("impact_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("trace_steps", sa.Column("user_visible_summary", sa.Text(), nullable=True))

    # ── bad_cases: Phase 2 source columns ───────────────────────────────
    op.add_column("bad_cases", sa.Column("source_memory_usage_event_id", postgresql.UUID, nullable=True))
    op.add_column("bad_cases", sa.Column("source_lifecycle_event_id", postgresql.UUID, nullable=True))
    op.add_column("bad_cases", sa.Column("candidate_for_phase3", sa.Boolean(), server_default=sa.text("true"), nullable=False))
    op.add_column("bad_cases", sa.Column("regression_seed_json", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False))

    op.create_foreign_key(
        "fk_bad_cases_source_memory_usage_event_id",
        "bad_cases", "memory_usage_events",
        ["source_memory_usage_event_id"], ["id"],
    )
    op.create_foreign_key(
        "fk_bad_cases_source_lifecycle_event_id",
        "bad_cases", "memory_lifecycle_events",
        ["source_lifecycle_event_id"], ["id"],
    )


def downgrade() -> None:
    """Drop all Phase 2 enhancement columns; drop relationship_explanation_events table."""

    # ── bad_cases: drop Phase 2 columns ──────────────────────────────────
    op.drop_constraint("fk_bad_cases_source_lifecycle_event_id", "bad_cases", type_="foreignkey")
    op.drop_constraint("fk_bad_cases_source_memory_usage_event_id", "bad_cases", type_="foreignkey")
    op.drop_column("bad_cases", "regression_seed_json")
    op.drop_column("bad_cases", "candidate_for_phase3")
    op.drop_column("bad_cases", "source_lifecycle_event_id")
    op.drop_column("bad_cases", "source_memory_usage_event_id")

    # ── trace_steps: drop Phase 2 columns ────────────────────────────────
    op.drop_column("trace_steps", "user_visible_summary")
    op.drop_column("trace_steps", "impact_json")
    op.drop_column("trace_steps", "lifecycle_event_ids")
    op.drop_column("trace_steps", "memory_usage_event_ids")
    op.drop_column("trace_steps", "feedback_event_ids")
    op.drop_column("trace_steps", "calibration_json")

    # ── boundary_settings: drop Phase 2 columns ──────────────────────────
    op.drop_column("boundary_settings", "meaningful_silence_enabled")
    op.drop_column("boundary_settings", "min_presence_interval_minutes")
    op.drop_column("boundary_settings", "max_presence_per_day")
    op.drop_column("boundary_settings", "continuity_visibility_policy")
    op.drop_column("boundary_settings", "feedback_usage_policy")
    op.drop_column("boundary_settings", "growth_confirmation_policy")
    op.drop_column("boundary_settings", "memory_confirmation_policy")
    op.drop_column("boundary_settings", "suppressed_presence_rules")
    # Note: suppressed_presence_types already existed in Phase 1, not dropped here
    op.drop_column("boundary_settings", "quiet_hours")

    # ── relationship_states: drop trend / explanation columns ────────────
    op.drop_constraint("fk_relationship_states_last_explanation_event_id", "relationship_states", type_="foreignkey")
    op.execute("ALTER TABLE relationship_states DROP CONSTRAINT IF EXISTS relationship_states_trend_check")
    op.drop_column("relationship_states", "last_changed_at")
    op.drop_column("relationship_states", "explanation_summary")
    op.drop_column("relationship_states", "last_explanation_event_id")
    op.drop_column("relationship_states", "continuity_trend")
    op.drop_column("relationship_states", "boundary_awareness_trend")
    op.drop_column("relationship_states", "emotional_closeness_trend")
    op.drop_column("relationship_states", "trust_trend")
    op.drop_column("relationship_states", "collaboration_trend")
    op.drop_column("relationship_states", "understanding_trend")
    op.drop_column("relationship_states", "familiarity_trend")

    # ── presence_opportunities: drop Phase 2 columns ─────────────────────
    op.drop_constraint("fk_presence_opportunities_feedback_event_id", "presence_opportunities", type_="foreignkey")
    op.execute("ALTER TABLE presence_opportunities DROP CONSTRAINT IF EXISTS presence_opportunities_timing_score_check")
    op.execute("ALTER TABLE presence_opportunities DROP CONSTRAINT IF EXISTS presence_opportunities_feedback_label_check")
    op.drop_column("presence_opportunities", "calibration_json")
    op.drop_column("presence_opportunities", "meaningful_silence_reason")
    op.drop_column("presence_opportunities", "opportunity_context_hash")
    op.drop_column("presence_opportunities", "type_affinity_snapshot")
    op.drop_column("presence_opportunities", "timing_score")
    op.drop_column("presence_opportunities", "feedback_label")
    op.drop_column("presence_opportunities", "feedback_event_id")
    op.drop_column("presence_opportunities", "suppress_type_rule_applied")
    op.drop_column("presence_opportunities", "accepted_at")
    op.drop_column("presence_opportunities", "dismissed_reason")
    op.drop_column("presence_opportunities", "dismissed_at")
    # Note: snoozed_until already existed in Phase 1, not dropped here

    # ── growth_records: drop Phase 2 columns ────────────────────────────
    op.drop_constraint("fk_growth_records_source_abstraction_candidate_id", "growth_records", type_="foreignkey")
    op.drop_column("growth_records", "revert_impact_json")
    op.drop_column("growth_records", "last_feedback_at")
    op.drop_column("growth_records", "feedback_score")
    op.drop_column("growth_records", "downstream_presence_opportunity_ids")
    op.drop_column("growth_records", "downstream_memory_ids")
    op.drop_column("growth_records", "downstream_trace_run_ids")
    op.drop_column("growth_records", "profile_version_after")
    op.drop_column("growth_records", "profile_version_before")
    op.drop_column("growth_records", "profile_patch_json")
    op.drop_column("growth_records", "source_abstraction_candidate_id")

    # ── growth_candidates: drop Phase 2 columns ──────────────────────────
    op.drop_constraint("fk_growth_candidates_source_abstraction_candidate_id", "growth_candidates", type_="foreignkey")
    op.drop_constraint("fk_growth_candidates_review_batch_id", "growth_candidates", type_="foreignkey")
    op.execute("ALTER TABLE growth_candidates DROP CONSTRAINT IF EXISTS growth_candidates_feedback_score_check")
    op.drop_column("growth_candidates", "calibration_json")
    op.drop_column("growth_candidates", "user_feedback_reason")
    op.drop_column("growth_candidates", "profile_patch_preview")
    op.drop_column("growth_candidates", "impact_preview_json")
    op.drop_column("growth_candidates", "negative_feedback_count")
    op.drop_column("growth_candidates", "positive_feedback_count")
    op.drop_column("growth_candidates", "feedback_score")
    op.drop_column("growth_candidates", "source_abstraction_candidate_id")
    op.drop_column("growth_candidates", "review_batch_id")

    # ── relationship_explanation_events ──────────────────────────────────
    op.execute("DROP INDEX IF EXISTS idx_relationship_explanation_events_evidence_memory_ids")
    op.drop_index("idx_relationship_explanation_events_trace", table_name="relationship_explanation_events")
    op.execute("DROP INDEX IF EXISTS idx_relationship_explanation_events_dimension")
    op.execute("DROP INDEX IF EXISTS idx_relationship_explanation_events_user_companion_created")
    op.drop_table("relationship_explanation_events")
