"""add_check_constraints_all_tables

Revision ID: 908db3efc215
Revises: 43ca2c981e85
Create Date: 2026-05-28 13:26:05.102580

Adds CHECK constraints to all Phase 1 core tables for enum-like fields.
All values follow docs/Echora 全局类型与枚举字典 V1.txt.
ModeKey does NOT include "voice" per global enum dictionary.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = "908db3efc215"
down_revision: Union[str, Sequence[str], None] = "43ca2c981e85"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ── Enum value lists (from global enum dictionary) ───────────────────

MODE_KEY_VALUES = (
    "project", "creative", "daily", "learning",
    "game", "character", "virtual_world",
)

CONVERSATION_STATUS_VALUES = ("active", "paused", "archived", "deleted")

MESSAGE_ROLE_VALUES = ("user", "assistant", "system", "tool")
MESSAGE_SOURCE_MODALITY_VALUES = ("text", "audio", "image", "video", "event")

MEMORY_TYPE_VALUES = (
    "fact", "preference", "goal", "episodic", "correction",
    "relationship", "emotional", "self", "project", "creative", "system",
)
MEMORY_STATE_VALUES = ("active", "dormant", "archived", "suppressed", "deleted")
MEMORY_VISIBILITY_VALUES = ("user_visible", "private_system", "sensitive")
MEMORY_CONSENT_VALUES = ("auto", "user_confirmed", "requires_review")

MEMORY_CANDIDATE_STATUS_VALUES = (
    "pending", "accepted", "edited", "rejected", "merged", "expired",
)
MEMORY_CANDIDATE_TYPE_VALUES = MEMORY_TYPE_VALUES
MEMORY_CANDIDATE_FEEDBACK_VALUES = (
    "positive", "weak_positive", "negative", "strong_negative",
)

GROWTH_TYPE_VALUES = (
    "understanding_update", "communication_style", "companion_strategy",
    "boundary_update", "self_narrative", "mode_strategy",
)
GROWTH_CANDIDATE_STATUS_VALUES = (
    "candidate", "committed", "rejected", "reverted", "observing",
)
GROWTH_RECORD_STATUS_VALUES = ("committed", "reverted")
GROWTH_RISK_VALUES = ("low", "medium", "high")

PRESENCE_TYPE_VALUES = (
    "continuation", "progress", "reflection", "memory_recall",
    "check_in", "creative_prompt", "boundary", "system",
)
PRESENCE_STATUS_VALUES = (
    "queued", "shown", "accepted", "dismissed",
    "snoozed", "suppressed", "expired",
)
PRESENCE_SURFACE_VALUES = ("hub", "queue", "notification", "inline")

RELATIONSHIP_DIMENSION_VALUES = (
    "familiarity", "understanding", "collaboration", "trust",
    "emotional_closeness", "boundary_awareness", "continuity",
)

TRACE_RUN_STATUS_VALUES = ("started", "completed", "failed", "cancelled")
TRACE_STEP_STATUS_VALUES = ("started", "completed", "failed", "skipped")

MEMORY_SAVE_POLICY_VALUES = ("review_all", "review_important", "auto_low_risk")
SENSITIVE_MEMORY_POLICY_VALUES = ("always_review", "never_save", "allow_with_warning")
PROACTIVE_LEVEL_VALUES = ("low", "medium", "high")
NOTIFICATION_SURFACE_VALUES = ("hub_queue_only", "allow_light_notification", "disabled")

BAD_CASE_TYPE_VALUES = (
    "wrong_memory", "false_memory", "outdated_memory_pollution",
    "correction_forgotten", "over_proactive", "over_flattering",
    "persona_drift", "wrong_growth", "boundary_issue",
    "retrieval_failure", "other",
)
BAD_CASE_SEVERITY_VALUES = ("low", "medium", "high", "critical")
BAD_CASE_STATUS_VALUES = ("open", "investigating", "resolved", "ignored")


# ── Helper: build CHECK constraint SQL ───────────────────────────────

def ck(table: str, column: str, values: tuple, name: str | None = None) -> str:
    """Build ADD CONSTRAINT SQL for a single-column CHECK."""
    vlist = ", ".join(f"'{v}'" for v in values)
    constraint_name = name or f"ck_{table}_{column}"
    return (
        f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} "
        f"CHECK ({column} IN ({vlist}))"
    )


def ck_range(table: str, column: str, low: float, high: float, name: str | None = None) -> str:
    """Build ADD CONSTRAINT SQL for a range CHECK."""
    constraint_name = name or f"ck_{table}_{column}_range"
    return (
        f"ALTER TABLE {table} ADD CONSTRAINT {constraint_name} "
        f"CHECK ({column} >= {low} AND {column} <= {high})"
    )


def upgrade() -> None:
    """Add CHECK constraints to all Phase 1 core tables."""

    # ── companions ────────────────────────────────────────────────
    op.execute(ck("companions", "current_mode", MODE_KEY_VALUES))

    # ── companion_modes ───────────────────────────────────────────
    op.execute(ck("companion_modes", "mode_key", MODE_KEY_VALUES))

    # ── conversations ─────────────────────────────────────────────
    op.execute(ck("conversations", "mode_key", MODE_KEY_VALUES))
    op.execute(ck("conversations", "status", CONVERSATION_STATUS_VALUES))

    # ── messages ──────────────────────────────────────────────────
    op.execute(ck("messages", "role", MESSAGE_ROLE_VALUES))
    op.execute(ck("messages", "source_modality", MESSAGE_SOURCE_MODALITY_VALUES))

    # ── memories ──────────────────────────────────────────────────
    op.execute(ck("memories", "type", MEMORY_TYPE_VALUES))
    op.execute(ck("memories", "state", MEMORY_STATE_VALUES))
    op.execute(ck("memories", "visibility", MEMORY_VISIBILITY_VALUES))
    op.execute(ck("memories", "consent_status", MEMORY_CONSENT_VALUES))
    op.execute(ck("memories", "source_modality", MESSAGE_SOURCE_MODALITY_VALUES))
    op.execute(ck_range("memories", "importance", 0, 1))
    op.execute(ck_range("memories", "confidence", 0, 1))
    op.execute(ck_range("memories", "emotional_intensity", 0, 1))
    op.execute(ck_range("memories", "goal_relevance", 0, 1))
    op.execute(ck_range("memories", "relationship_impact", 0, 1))
    op.execute(ck_range("memories", "correction_value", 0, 1))
    op.execute(ck_range("memories", "memory_strength", 0, 1))

    # ── memory_candidates ─────────────────────────────────────────
    op.execute(ck("memory_candidates", "status", MEMORY_CANDIDATE_STATUS_VALUES))
    op.execute(ck("memory_candidates", "suggested_type", MEMORY_CANDIDATE_TYPE_VALUES))
    op.execute(ck_range("memory_candidates", "importance", 0, 1))
    op.execute(ck_range("memory_candidates", "confidence", 0, 1))
    op.execute(ck_range("memory_candidates", "emotional_intensity", 0, 1))
    op.execute(ck_range("memory_candidates", "goal_relevance", 0, 1))
    op.execute(ck_range("memory_candidates", "relationship_impact", 0, 1))
    op.execute(ck_range("memory_candidates", "correction_value", 0, 1))
    op.execute(ck_range("memory_candidates", "novelty", 0, 1))
    op.execute(ck_range("memory_candidates", "recurrence", 0, 1))
    op.execute(ck_range("memory_candidates", "triviality", 0, 1))
    op.execute(ck_range("memory_candidates", "sensitivity_risk", 0, 1))
    op.execute(ck_range("memory_candidates", "score", 0, 1))

    # ── growth_candidates ─────────────────────────────────────────
    op.execute(ck("growth_candidates", "type", GROWTH_TYPE_VALUES))
    op.execute(ck("growth_candidates", "status", GROWTH_CANDIDATE_STATUS_VALUES))
    op.execute(ck("growth_candidates", "risk_level", GROWTH_RISK_VALUES))
    op.execute(ck_range("growth_candidates", "confidence", 0, 1))
    op.execute(ck_range("growth_candidates", "evidence_score", 0, 1))

    # ── growth_records ────────────────────────────────────────────
    op.execute(ck("growth_records", "type", GROWTH_TYPE_VALUES))
    op.execute(ck("growth_records", "status", GROWTH_RECORD_STATUS_VALUES))

    # ── relationship_events ───────────────────────────────────────
    op.execute(ck("relationship_events", "dimension", RELATIONSHIP_DIMENSION_VALUES))

    # ── relationship_states ───────────────────────────────────────
    op.execute(ck_range("relationship_states", "familiarity", 0, 1))
    op.execute(ck_range("relationship_states", "understanding", 0, 1))
    op.execute(ck_range("relationship_states", "collaboration", 0, 1))
    op.execute(ck_range("relationship_states", "trust", 0, 1))
    op.execute(ck_range("relationship_states", "emotional_closeness", 0, 1))
    op.execute(ck_range("relationship_states", "boundary_awareness", 0, 1))
    op.execute(ck_range("relationship_states", "continuity", 0, 1))

    # ── presence_opportunities ────────────────────────────────────
    op.execute(ck("presence_opportunities", "type", PRESENCE_TYPE_VALUES))
    op.execute(ck("presence_opportunities", "status", PRESENCE_STATUS_VALUES))
    op.execute(ck("presence_opportunities", "recommended_surface", PRESENCE_SURFACE_VALUES))
    op.execute(ck_range("presence_opportunities", "priority", 0, 1))
    op.execute(ck_range("presence_opportunities", "urgency", 0, 1))
    op.execute(ck_range("presence_opportunities", "sensitivity", 0, 1))
    op.execute(ck_range("presence_opportunities", "interruption_risk", 0, 1))

    # ── boundary_settings ─────────────────────────────────────────
    op.execute(ck("boundary_settings", "memory_save_policy", MEMORY_SAVE_POLICY_VALUES))
    op.execute(ck("boundary_settings", "sensitive_memory_policy", SENSITIVE_MEMORY_POLICY_VALUES))
    op.execute(ck("boundary_settings", "proactive_level", PROACTIVE_LEVEL_VALUES))
    op.execute(ck("boundary_settings", "notification_surface", NOTIFICATION_SURFACE_VALUES))

    # ── trace_runs / trace_steps ──────────────────────────────────
    op.execute(ck("trace_runs", "status", TRACE_RUN_STATUS_VALUES))
    op.execute(ck("trace_steps", "status", TRACE_STEP_STATUS_VALUES))

    # ── bad_cases ─────────────────────────────────────────────────
    op.execute(ck("bad_cases", "type", BAD_CASE_TYPE_VALUES))
    op.execute(ck("bad_cases", "severity", BAD_CASE_SEVERITY_VALUES))
    op.execute(ck("bad_cases", "status", BAD_CASE_STATUS_VALUES))

    # ── relationship_states unique constraint (if missing) ────────
    # The migration already creates UNIQUE(user_id, companion_id);
    # this is just a safety check — it will fail harmlessly if exists.


def downgrade() -> None:
    """Drop all CHECK constraints added in this migration."""

    checks = [
        # companions
        ("companions", "current_mode"),
        # companion_modes
        ("companion_modes", "mode_key"),
        # conversations
        ("conversations", "mode_key"),
        ("conversations", "status"),
        # messages
        ("messages", "role"),
        ("messages", "source_modality"),
        # memories
        ("memories", "type"), ("memories", "state"), ("memories", "visibility"),
        ("memories", "consent_status"), ("memories", "source_modality"),
        ("memories", "importance_range"), ("memories", "confidence_range"),
        ("memories", "emotional_intensity_range"), ("memories", "goal_relevance_range"),
        ("memories", "relationship_impact_range"), ("memories", "correction_value_range"),
        ("memories", "memory_strength_range"),
        # memory_candidates
        ("memory_candidates", "status"), ("memory_candidates", "suggested_type"),
        ("memory_candidates", "importance_range"), ("memory_candidates", "confidence_range"),
        ("memory_candidates", "emotional_intensity_range"), ("memory_candidates", "goal_relevance_range"),
        ("memory_candidates", "relationship_impact_range"), ("memory_candidates", "correction_value_range"),
        ("memory_candidates", "novelty_range"), ("memory_candidates", "recurrence_range"),
        ("memory_candidates", "triviality_range"), ("memory_candidates", "sensitivity_risk_range"),
        ("memory_candidates", "score_range"),
        # growth_candidates
        ("growth_candidates", "type"), ("growth_candidates", "status"), ("growth_candidates", "risk_level"),
        ("growth_candidates", "confidence_range"), ("growth_candidates", "evidence_score_range"),
        # growth_records
        ("growth_records", "type"), ("growth_records", "status"),
        # relationship_events
        ("relationship_events", "dimension"),
        # relationship_states ranges
        ("relationship_states", "familiarity_range"), ("relationship_states", "understanding_range"),
        ("relationship_states", "collaboration_range"), ("relationship_states", "trust_range"),
        ("relationship_states", "emotional_closeness_range"), ("relationship_states", "boundary_awareness_range"),
        ("relationship_states", "continuity_range"),
        # presence_opportunities
        ("presence_opportunities", "type"), ("presence_opportunities", "status"),
        ("presence_opportunities", "recommended_surface"),
        ("presence_opportunities", "priority_range"), ("presence_opportunities", "urgency_range"),
        ("presence_opportunities", "sensitivity_range"), ("presence_opportunities", "interruption_risk_range"),
        # boundary_settings
        ("boundary_settings", "memory_save_policy"), ("boundary_settings", "sensitive_memory_policy"),
        ("boundary_settings", "proactive_level"), ("boundary_settings", "notification_surface"),
        # trace
        ("trace_runs", "status"), ("trace_steps", "status"),
        # bad_cases
        ("bad_cases", "type"), ("bad_cases", "severity"), ("bad_cases", "status"),
    ]

    for table, col in checks:
        op.execute(
            f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS ck_{table}_{col}"
        )
