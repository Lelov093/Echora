"""phase4_04_persona_growth_presence_schema

Revision ID: p4_04_persona_growth_presence
Revises: p4_03_co_presence
Create Date: 2026-06-01 00:00:00.000000

Create Phase 4 Reoriented persona growth / drift guard / mutual presence
schema without entering API or service implementation.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p4_04_persona_growth_presence"
down_revision: Union[str, Sequence[str], None] = "p4_03_co_presence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PERSONA_GROWTH_DIMENSION_VALUES = (
    "persona_summary",
    "presence_style",
    "boundary_alignment",
    "relationship_contract",
    "scene_behavior",
)
IMPACT_LEVEL_VALUES = ("low", "medium", "high", "critical")
PERSONA_GROWTH_STATUS_VALUES = ("pending_review", "approved", "rejected", "committed", "archived")
PERSONA_EVENT_TYPE_VALUES = (
    "candidate_committed",
    "reverted",
    "manual_adjustment",
    "drift_correction",
    "review_approved",
)

DRIFT_RISK_LEVEL_VALUES = ("low", "medium", "high", "critical")
DRIFT_STATUS_VALUES = ("pending", "passed", "review_required", "blocked", "overridden")
DRIFT_BASELINE_VALUES = ("persona_profile", "relationship_contract", "shared_scene", "shared_experience")

CONSISTENCY_SCOPE_VALUES = ("co_presence_session", "shared_scene", "delegated_execution")
CONSISTENCY_STATUS_VALUES = ("pending", "passed", "review_required", "blocked")

COMPANION_PRESENCE_ORIGIN_VALUES = ("companion_private", "co_presence", "shared_scene", "delegated_execution", "manual")
COMPANION_PRESENCE_MODE_VALUES = (
    "solo_checkin",
    "co_present_invitation",
    "observer_support",
    "repair",
    "celebration",
    "reflection",
    "delegation_followup",
)
OPPORTUNITY_STATUS_VALUES = ("queued", "accepted", "dismissed", "snoozed", "expired", "converted")
PRESENCE_SURFACE_VALUES = ("hub_queue", "session_surface", "scene_panel", "silent")

CO_PRESENCE_OPPORTUNITY_TYPE_VALUES = (
    "invite_active_companion",
    "invite_observing_companion",
    "scene_resume",
    "shared_reflection",
    "joint_delegation",
)
CO_PRESENCE_TARGET_ROLE_VALUES = ("active_companion", "observing_companion", "delegated_executor")

MUTUAL_POLICY_SCOPE_VALUES = ("companion_presence", "co_presence", "shared_scene", "group_consistency")
LEARNING_MODE_VALUES = ("disabled", "shadow", "assistive", "active")
MUTUAL_SELECTED_ACTION_VALUES = ("queue", "invite_scene", "defer", "silence", "review_required")
MUTUAL_POLICY_STATUS_VALUES = ("created", "completed", "failed", "cancelled", "review_required")

PRESENCE_FEEDBACK_TYPE_VALUES = (
    "accept",
    "dismiss",
    "snooze",
    "suppress_type",
    "good_timing",
    "bad_timing",
    "too_much",
    "too_little",
)
FEEDBACK_SOURCE_VALUES = ("user", "system", "session_review")


def ck(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=name)


def upgrade() -> None:
    op.create_table(
        "companion_persona_growth_candidates",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("source_growth_candidate_id", postgresql.UUID, nullable=True),
        sa.Column("shared_experience_record_id", postgresql.UUID, nullable=True),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=True),
        sa.Column("source_trace_run_id", postgresql.UUID, nullable=True),
        sa.Column("growth_dimension", sa.Text(), nullable=False, server_default=sa.text("'persona_summary'")),
        sa.Column("impact_level", sa.Text(), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("candidate_status", sa.Text(), nullable=False, server_default=sa.text("'pending_review'")),
        sa.Column("growth_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("evidence_summary", sa.Text(), nullable=True),
        sa.Column("proposed_persona_patch_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("proposed_presence_patch_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("confidence", sa.Double(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("evidence_score", sa.Double(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("requires_user_review", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["source_growth_candidate_id"], ["growth_candidates.id"]),
        sa.ForeignKeyConstraint(["shared_experience_record_id"], ["shared_experience_records.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["source_trace_run_id"], ["trace_runs.id"]),
        ck("growth_dimension", PERSONA_GROWTH_DIMENSION_VALUES, "ck_cpgc_dimension"),
        ck("impact_level", IMPACT_LEVEL_VALUES, "ck_cpgc_impact"),
        ck("candidate_status", PERSONA_GROWTH_STATUS_VALUES, "ck_cpgc_status"),
        sa.CheckConstraint(
            "(impact_level NOT IN ('high', 'critical') OR requires_user_review = true)",
            name="ck_cpgc_high_review",
        ),
    )
    op.create_index(
        "idx_cpgc_companion_status",
        "companion_persona_growth_candidates",
        ["companion_id", "candidate_status", "created_at"],
    )

    op.create_table(
        "companion_persona_growth_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("source_persona_growth_candidate_id", postgresql.UUID, nullable=True),
        sa.Column("source_growth_record_id", postgresql.UUID, nullable=True),
        sa.Column("source_trace_run_id", postgresql.UUID, nullable=True),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False, server_default=sa.text("'candidate_committed'")),
        sa.Column("impact_level", sa.Text(), nullable=False, server_default=sa.text("'medium'")),
        sa.Column("event_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("applied_patch_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["source_persona_growth_candidate_id"], ["companion_persona_growth_candidates.id"]),
        sa.ForeignKeyConstraint(["source_growth_record_id"], ["growth_records.id"]),
        sa.ForeignKeyConstraint(["source_trace_run_id"], ["trace_runs.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        ck("event_type", PERSONA_EVENT_TYPE_VALUES, "ck_cpge_type"),
        ck("impact_level", IMPACT_LEVEL_VALUES, "ck_cpge_impact"),
        sa.CheckConstraint(
            "(impact_level NOT IN ('high', 'critical') OR review_required = true)",
            name="ck_cpge_high_review",
        ),
    )
    op.create_index(
        "idx_cpge_companion_created",
        "companion_persona_growth_events",
        ["companion_id", "occurred_at"],
    )

    op.create_table(
        "companion_persona_drift_checks",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("source_trace_run_id", postgresql.UUID, nullable=True),
        sa.Column("source_growth_candidate_id", postgresql.UUID, nullable=True),
        sa.Column("source_persona_growth_candidate_id", postgresql.UUID, nullable=True),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=True),
        sa.Column("shared_scene_id", postgresql.UUID, nullable=True),
        sa.Column("drift_risk_level", sa.Text(), nullable=False, server_default=sa.text("'low'")),
        sa.Column("check_status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("baseline_source", sa.Text(), nullable=False, server_default=sa.text("'persona_profile'")),
        sa.Column("drift_score", sa.Double(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("requires_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("blocks_auto_apply", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("drift_summary", sa.Text(), nullable=True),
        sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("recommendation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["source_trace_run_id"], ["trace_runs.id"]),
        sa.ForeignKeyConstraint(["source_growth_candidate_id"], ["growth_candidates.id"]),
        sa.ForeignKeyConstraint(["source_persona_growth_candidate_id"], ["companion_persona_growth_candidates.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["shared_scene_id"], ["shared_scenes.id"]),
        ck("drift_risk_level", DRIFT_RISK_LEVEL_VALUES, "ck_cpdc_risk"),
        ck("check_status", DRIFT_STATUS_VALUES, "ck_cpdc_status"),
        ck("baseline_source", DRIFT_BASELINE_VALUES, "ck_cpdc_baseline"),
        sa.CheckConstraint(
            "(drift_risk_level NOT IN ('high', 'critical') OR (requires_review = true AND blocks_auto_apply = true))",
            name="ck_cpdc_high_guard",
        ),
    )
    op.create_index(
        "idx_cpdc_companion_status",
        "companion_persona_drift_checks",
        ["companion_id", "check_status", "created_at"],
    )

    op.create_table(
        "group_persona_consistency_checks",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=True),
        sa.Column("shared_scene_id", postgresql.UUID, nullable=True),
        sa.Column("source_trace_run_id", postgresql.UUID, nullable=True),
        sa.Column("consistency_scope", sa.Text(), nullable=False, server_default=sa.text("'co_presence_session'")),
        sa.Column("check_status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("consistency_score", sa.Double(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("affected_companion_ids", postgresql.ARRAY(postgresql.UUID), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("requires_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("consistency_summary", sa.Text(), nullable=True),
        sa.Column("conflict_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("recommendation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["shared_scene_id"], ["shared_scenes.id"]),
        sa.ForeignKeyConstraint(["source_trace_run_id"], ["trace_runs.id"]),
        ck("consistency_scope", CONSISTENCY_SCOPE_VALUES, "ck_gpcc_scope"),
        ck("check_status", CONSISTENCY_STATUS_VALUES, "ck_gpcc_status"),
        sa.CheckConstraint(
            "(co_presence_session_id IS NOT NULL OR shared_scene_id IS NOT NULL OR source_trace_run_id IS NOT NULL)",
            name="ck_gpcc_source_ref",
        ),
    )
    op.create_index(
        "idx_gpcc_session_status",
        "group_persona_consistency_checks",
        ["co_presence_session_id", "check_status", "created_at"],
    )

    op.create_table(
        "mutual_presence_policy_runs",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("primary_companion_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=True),
        sa.Column("shared_scene_id", postgresql.UUID, nullable=True),
        sa.Column("trace_run_id", postgresql.UUID, nullable=True),
        sa.Column("source_presence_policy_run_id", postgresql.UUID, nullable=True),
        sa.Column("presence_opportunity_id", postgresql.UUID, nullable=True),
        sa.Column("policy_scope", sa.Text(), nullable=False, server_default=sa.text("'companion_presence'")),
        sa.Column("learning_mode", sa.Text(), nullable=False, server_default=sa.text("'assistive'")),
        sa.Column("selected_action", sa.Text(), nullable=False, server_default=sa.text("'queue'")),
        sa.Column("policy_status", sa.Text(), nullable=False, server_default=sa.text("'created'")),
        sa.Column("reward_prediction", sa.Double(), nullable=True),
        sa.Column("mutuality_score", sa.Double(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("interruption_risk", sa.Double(), nullable=False, server_default=sa.text("0.0")),
        sa.Column("presence_value", sa.Double(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("explanation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("boundary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("signal_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["primary_companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["shared_scene_id"], ["shared_scenes.id"]),
        sa.ForeignKeyConstraint(["trace_run_id"], ["trace_runs.id"]),
        sa.ForeignKeyConstraint(["source_presence_policy_run_id"], ["presence_policy_runs.id"]),
        sa.ForeignKeyConstraint(["presence_opportunity_id"], ["presence_opportunities.id"]),
        ck("policy_scope", MUTUAL_POLICY_SCOPE_VALUES, "ck_mppr_scope"),
        ck("learning_mode", LEARNING_MODE_VALUES, "ck_mppr_learning"),
        ck("selected_action", MUTUAL_SELECTED_ACTION_VALUES, "ck_mppr_action"),
        ck("policy_status", MUTUAL_POLICY_STATUS_VALUES, "ck_mppr_status"),
        sa.CheckConstraint(
            "(reward_prediction IS NULL OR reward_prediction BETWEEN -1 AND 1)",
            name="ck_mppr_reward",
        ),
    )
    op.create_index(
        "idx_mppr_trace_status",
        "mutual_presence_policy_runs",
        ["trace_run_id", "policy_status", "created_at"],
    )

    op.create_table(
        "companion_presence_opportunities",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("base_presence_opportunity_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=True),
        sa.Column("shared_scene_id", postgresql.UUID, nullable=True),
        sa.Column("mutual_presence_policy_run_id", postgresql.UUID, nullable=True),
        sa.Column("opportunity_origin", sa.Text(), nullable=False, server_default=sa.text("'companion_private'")),
        sa.Column("presence_mode", sa.Text(), nullable=False, server_default=sa.text("'solo_checkin'")),
        sa.Column("opportunity_status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("recommended_surface", sa.Text(), nullable=False, server_default=sa.text("'hub_queue'")),
        sa.Column("requires_user_confirmation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("rationale_summary", sa.Text(), nullable=True),
        sa.Column("presence_context_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["base_presence_opportunity_id"], ["presence_opportunities.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["shared_scene_id"], ["shared_scenes.id"]),
        sa.ForeignKeyConstraint(["mutual_presence_policy_run_id"], ["mutual_presence_policy_runs.id"]),
        sa.UniqueConstraint("base_presence_opportunity_id", name="uq_cpro_base_presence"),
        ck("opportunity_origin", COMPANION_PRESENCE_ORIGIN_VALUES, "ck_cpro_origin"),
        ck("presence_mode", COMPANION_PRESENCE_MODE_VALUES, "ck_cpro_mode"),
        ck("opportunity_status", OPPORTUNITY_STATUS_VALUES, "ck_cpro_status"),
        ck("recommended_surface", PRESENCE_SURFACE_VALUES, "ck_cpro_surface"),
    )
    op.create_index(
        "idx_cpro_companion_status",
        "companion_presence_opportunities",
        ["companion_id", "opportunity_status", "created_at"],
    )

    op.create_table(
        "co_presence_opportunities",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("primary_companion_id", postgresql.UUID, nullable=False),
        sa.Column("base_presence_opportunity_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=True),
        sa.Column("shared_scene_id", postgresql.UUID, nullable=True),
        sa.Column("target_companion_id", postgresql.UUID, nullable=True),
        sa.Column("mutual_presence_policy_run_id", postgresql.UUID, nullable=True),
        sa.Column("opportunity_type", sa.Text(), nullable=False, server_default=sa.text("'invite_active_companion'")),
        sa.Column("opportunity_status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("target_role", sa.Text(), nullable=False, server_default=sa.text("'active_companion'")),
        sa.Column("recommended_surface", sa.Text(), nullable=False, server_default=sa.text("'hub_queue'")),
        sa.Column("requires_user_confirmation", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("rationale_summary", sa.Text(), nullable=True),
        sa.Column("boundary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["primary_companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["base_presence_opportunity_id"], ["presence_opportunities.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["shared_scene_id"], ["shared_scenes.id"]),
        sa.ForeignKeyConstraint(["target_companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["mutual_presence_policy_run_id"], ["mutual_presence_policy_runs.id"]),
        sa.UniqueConstraint("base_presence_opportunity_id", name="uq_copo_base_presence"),
        ck("opportunity_type", CO_PRESENCE_OPPORTUNITY_TYPE_VALUES, "ck_copo_type"),
        ck("opportunity_status", OPPORTUNITY_STATUS_VALUES, "ck_copo_status"),
        ck("target_role", CO_PRESENCE_TARGET_ROLE_VALUES, "ck_copo_role"),
        ck("recommended_surface", PRESENCE_SURFACE_VALUES, "ck_copo_surface"),
        sa.CheckConstraint(
            "("
            "(target_role IN ('active_companion', 'observing_companion') AND target_companion_id IS NOT NULL)"
            " OR "
            "(target_role = 'delegated_executor' AND target_companion_id IS NULL)"
            ")",
            name="ck_copo_target",
        ),
    )
    op.create_index(
        "idx_copo_primary_status",
        "co_presence_opportunities",
        ["primary_companion_id", "opportunity_status", "created_at"],
    )

    op.create_table(
        "companion_presence_feedback_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("base_presence_opportunity_id", postgresql.UUID, nullable=True),
        sa.Column("companion_presence_opportunity_id", postgresql.UUID, nullable=True),
        sa.Column("co_presence_opportunity_id", postgresql.UUID, nullable=True),
        sa.Column("mutual_presence_policy_run_id", postgresql.UUID, nullable=True),
        sa.Column("feedback_event_id", postgresql.UUID, nullable=True),
        sa.Column("feedback_type", sa.Text(), nullable=False, server_default=sa.text("'accept'")),
        sa.Column("feedback_source", sa.Text(), nullable=False, server_default=sa.text("'user'")),
        sa.Column("feedback_strength", sa.Double(), nullable=True),
        sa.Column("feedback_note", sa.Text(), nullable=True),
        sa.Column("feedback_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["base_presence_opportunity_id"], ["presence_opportunities.id"]),
        sa.ForeignKeyConstraint(["companion_presence_opportunity_id"], ["companion_presence_opportunities.id"]),
        sa.ForeignKeyConstraint(["co_presence_opportunity_id"], ["co_presence_opportunities.id"]),
        sa.ForeignKeyConstraint(["mutual_presence_policy_run_id"], ["mutual_presence_policy_runs.id"]),
        sa.ForeignKeyConstraint(["feedback_event_id"], ["feedback_events.id"]),
        ck("feedback_type", PRESENCE_FEEDBACK_TYPE_VALUES, "ck_cpfe_type"),
        ck("feedback_source", FEEDBACK_SOURCE_VALUES, "ck_cpfe_source"),
        sa.CheckConstraint(
            "(feedback_strength IS NULL OR feedback_strength BETWEEN -1 AND 1)",
            name="ck_cpfe_strength",
        ),
        sa.CheckConstraint(
            "("
            "base_presence_opportunity_id IS NOT NULL "
            "OR companion_presence_opportunity_id IS NOT NULL "
            "OR co_presence_opportunity_id IS NOT NULL "
            "OR mutual_presence_policy_run_id IS NOT NULL "
            "OR feedback_event_id IS NOT NULL"
            ")",
            name="ck_cpfe_ref",
        ),
    )
    op.create_index(
        "idx_cpfe_companion_created",
        "companion_presence_feedback_events",
        ["companion_id", "created_at"],
    )

    op.add_column("presence_opportunities", sa.Column("co_presence_session_id", postgresql.UUID, nullable=True))
    op.create_foreign_key(
        "fk_presence_opportunities_co_presence_session_id",
        "presence_opportunities",
        "co_presence_sessions",
        ["co_presence_session_id"],
        ["id"],
    )
    op.create_index(
        "idx_presence_opportunities_co_presence",
        "presence_opportunities",
        ["co_presence_session_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_presence_opportunities_co_presence", table_name="presence_opportunities")
    op.drop_constraint(
        "fk_presence_opportunities_co_presence_session_id",
        "presence_opportunities",
        type_="foreignkey",
    )
    op.drop_column("presence_opportunities", "co_presence_session_id")

    op.drop_index("idx_cpfe_companion_created", table_name="companion_presence_feedback_events")
    op.drop_table("companion_presence_feedback_events")

    op.drop_index("idx_copo_primary_status", table_name="co_presence_opportunities")
    op.drop_table("co_presence_opportunities")

    op.drop_index("idx_cpro_companion_status", table_name="companion_presence_opportunities")
    op.drop_table("companion_presence_opportunities")

    op.drop_index("idx_mppr_trace_status", table_name="mutual_presence_policy_runs")
    op.drop_table("mutual_presence_policy_runs")

    op.drop_index("idx_gpcc_session_status", table_name="group_persona_consistency_checks")
    op.drop_table("group_persona_consistency_checks")

    op.drop_index("idx_cpdc_companion_status", table_name="companion_persona_drift_checks")
    op.drop_table("companion_persona_drift_checks")

    op.drop_index("idx_cpge_companion_created", table_name="companion_persona_growth_events")
    op.drop_table("companion_persona_growth_events")

    op.drop_index("idx_cpgc_companion_status", table_name="companion_persona_growth_candidates")
    op.drop_table("companion_persona_growth_candidates")
