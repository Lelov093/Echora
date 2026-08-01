"""phase4_03_co_presence_schema

Revision ID: p4_03_co_presence
Revises: p4_02_companion_memory
Create Date: 2026-06-01 00:00:00.000000

Create Phase 4 Reoriented co-presence/session/shared-scene/participant
awareness schema and connect shared experience sources without entering API
or service implementation.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p4_03_co_presence"
down_revision: Union[str, Sequence[str], None] = "p4_02_companion_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


SESSION_STATUS_VALUES = ("draft", "active", "paused", "ended", "archived")
SESSION_SOURCE_VALUES = ("direct_conversation", "shared_scene", "delegated_execution", "manual", "imported")
VISIBILITY_SCOPE_VALUES = ("hidden", "participant_list", "role_summary", "full_scene")

PARTICIPANT_TYPE_VALUES = ("user", "companion", "external_agent")
PARTICIPANT_ROLE_VALUES = (
    "user",
    "primary_companion",
    "active_companion",
    "observing_companion",
    "delegated_executor",
)
JOIN_STATUS_VALUES = ("invited", "active", "paused", "left", "removed")

AWARENESS_TYPE_VALUES = ("participant_presence", "scene_context", "memory_boundary", "delegation_boundary")
AWARENESS_LEVEL_VALUES = ("full", "partial", "minimal", "hidden")
AWARENESS_STATUS_VALUES = ("active", "stale", "suppressed")
AWARENESS_SOURCE_VALUES = ("system", "user", "companion", "delegated_executor")

SCENE_TYPE_VALUES = ("conversation", "workspace", "activity", "delegation", "reflection")
SCENE_STATUS_VALUES = ("draft", "active", "paused", "completed", "archived")
SCENE_SOURCE_VALUES = ("co_presence_session", "manual", "delegated_execution", "conversation_context")
SCENE_EVENT_TYPE_VALUES = ("utterance", "state_change", "task_action", "delegation_event", "memory_event", "scene_note")
SCENE_EVENT_SOURCE_VALUES = ("user", "companion", "system", "delegated_executor")

EXPERIENCE_SOURCE_VALUES = ("session", "scene_event", "delegation_result", "manual_capture", "conversation")
EXPERIENCE_STATUS_VALUES = ("captured", "candidate_pending_review", "approved", "rejected", "archived")
EXPERIENCE_MEMORY_ACTION_VALUES = ("none", "shared_candidate", "private_candidate", "both")

PERMISSION_SOURCE_VALUES = ("session_default", "session_override", "user_override", "review_decision")
MEMORY_PARTICIPATION_VALUES = (
    "none",
    "working_memory_only",
    "candidate_only",
    "shared_candidate_allowed",
    "private_candidate_allowed",
)

POLICY_STATUS_VALUES = ("active", "archived")
SESSION_GLOBAL_MEMORY_SCOPE_VALUES = ("none", "low_risk_summary_only", "policy_authorized")
CROSS_PRIVATE_READ_POLICY_VALUES = ("deny", "review_required", "explicit_user_authorization")
MEMORY_SYNC_POLICY_VALUES = ("review_required", "explicit_user_authorization", "deny")


def ck(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=name)


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION phase4_set_memory_owner_defaults()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.owner_companion_id IS NULL THEN
                NEW.owner_companion_id := NEW.companion_id;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_phase4_memories_owner_defaults ON memories;
        CREATE TRIGGER trg_phase4_memories_owner_defaults
        BEFORE INSERT OR UPDATE ON memories
        FOR EACH ROW
        EXECUTE FUNCTION phase4_set_memory_owner_defaults();
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION phase4_set_memory_candidate_owner_defaults()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF NEW.proposed_owner_companion_id IS NULL THEN
                NEW.proposed_owner_companion_id := NEW.companion_id;
            END IF;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        DROP TRIGGER IF EXISTS trg_phase4_memory_candidates_owner_defaults ON memory_candidates;
        CREATE TRIGGER trg_phase4_memory_candidates_owner_defaults
        BEFORE INSERT OR UPDATE ON memory_candidates
        FOR EACH ROW
        EXECUTE FUNCTION phase4_set_memory_candidate_owner_defaults();
        """
    )
    op.execute("UPDATE memories SET owner_companion_id = companion_id WHERE owner_companion_id IS NULL")
    op.execute(
        "UPDATE memory_candidates SET proposed_owner_companion_id = companion_id "
        "WHERE proposed_owner_companion_id IS NULL"
    )
    op.alter_column("memories", "owner_companion_id", nullable=False)
    op.alter_column("memory_candidates", "proposed_owner_companion_id", nullable=False)

    op.create_table(
        "co_presence_sessions",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("primary_companion_id", postgresql.UUID, nullable=False),
        sa.Column("originating_conversation_id", postgresql.UUID, nullable=True),
        sa.Column("session_title", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("session_summary", sa.Text(), nullable=True),
        sa.Column("session_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("session_source", sa.Text(), nullable=False, server_default=sa.text("'direct_conversation'")),
        sa.Column("visibility_scope", sa.Text(), nullable=False, server_default=sa.text("'role_summary'")),
        sa.Column("entry_reason", sa.Text(), nullable=True),
        sa.Column("participant_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("boundary_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["primary_companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["originating_conversation_id"], ["conversations.id"]),
        ck("session_status", SESSION_STATUS_VALUES, "ck_cps_status"),
        ck("session_source", SESSION_SOURCE_VALUES, "ck_cps_source"),
        ck("visibility_scope", VISIBILITY_SCOPE_VALUES, "ck_cps_visibility"),
    )
    op.create_index("idx_cps_user_status", "co_presence_sessions", ["user_id", "session_status", "started_at"])
    op.create_index(
        "idx_cps_primary_companion_status",
        "co_presence_sessions",
        ["primary_companion_id", "session_status", "started_at"],
    )

    op.create_table(
        "co_presence_participants",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=False),
        sa.Column("participant_type", sa.Text(), nullable=False),
        sa.Column("participant_role", sa.Text(), nullable=False, server_default=sa.text("'active_companion'")),
        sa.Column("participant_user_id", postgresql.UUID, nullable=True),
        sa.Column("participant_companion_id", postgresql.UUID, nullable=True),
        sa.Column("external_agent_label", sa.Text(), nullable=True),
        sa.Column("join_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("visibility_scope", sa.Text(), nullable=False, server_default=sa.text("'role_summary'")),
        sa.Column("can_speak", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("can_delegate", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_override_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["participant_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["participant_companion_id"], ["companions.id"]),
        ck("participant_type", PARTICIPANT_TYPE_VALUES, "ck_copp_type"),
        ck("participant_role", PARTICIPANT_ROLE_VALUES, "ck_copp_role"),
        ck("join_status", JOIN_STATUS_VALUES, "ck_copp_join"),
        ck("visibility_scope", VISIBILITY_SCOPE_VALUES, "ck_copp_visibility"),
        sa.CheckConstraint(
            "("
            "(participant_type = 'user' AND participant_user_id IS NOT NULL AND participant_companion_id IS NULL AND external_agent_label IS NULL)"
            " OR "
            "(participant_type = 'companion' AND participant_user_id IS NULL AND participant_companion_id IS NOT NULL AND external_agent_label IS NULL)"
            " OR "
            "(participant_type = 'external_agent' AND participant_user_id IS NULL AND participant_companion_id IS NULL AND NULLIF(TRIM(COALESCE(external_agent_label, '')), '') IS NOT NULL)"
            ")",
            name="ck_copp_subject",
        ),
        sa.CheckConstraint(
            "("
            "(participant_role = 'user' AND participant_type = 'user')"
            " OR "
            "(participant_role IN ('primary_companion', 'active_companion', 'observing_companion') AND participant_type = 'companion')"
            " OR "
            "(participant_role = 'delegated_executor' AND participant_type = 'external_agent')"
            ")",
            name="ck_copp_role_match",
        ),
    )
    op.create_index(
        "idx_copp_session_role",
        "co_presence_participants",
        ["co_presence_session_id", "participant_role", "join_status"],
    )

    op.create_table(
        "co_presence_session_policies",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=False),
        sa.Column("policy_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column(
            "default_primary_memory_participation",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'private_candidate_allowed'"),
        ),
        sa.Column(
            "default_active_memory_participation",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'shared_candidate_allowed'"),
        ),
        sa.Column(
            "default_observing_memory_participation",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'none'"),
        ),
        sa.Column(
            "default_delegated_memory_participation",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'candidate_only'"),
        ),
        sa.Column(
            "user_global_memory_scope",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'low_risk_summary_only'"),
        ),
        sa.Column(
            "cross_companion_private_read_policy",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'deny'"),
        ),
        sa.Column(
            "private_to_shared_policy",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'review_required'"),
        ),
        sa.Column(
            "shared_to_private_policy",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'review_required'"),
        ),
        sa.Column(
            "allow_observing_companion_long_term_memory",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "allow_autonomous_companion_interaction",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "session_visibility_policy_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "boundary_policy_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.UniqueConstraint("co_presence_session_id", name="uq_cpsp_session"),
        ck("policy_status", POLICY_STATUS_VALUES, "ck_cpsp_status"),
        ck("default_primary_memory_participation", MEMORY_PARTICIPATION_VALUES, "ck_cpsp_primary_participation"),
        ck("default_active_memory_participation", MEMORY_PARTICIPATION_VALUES, "ck_cpsp_active_participation"),
        ck("default_observing_memory_participation", MEMORY_PARTICIPATION_VALUES, "ck_cpsp_observing_participation"),
        ck("default_delegated_memory_participation", MEMORY_PARTICIPATION_VALUES, "ck_cpsp_delegated_participation"),
        ck("user_global_memory_scope", SESSION_GLOBAL_MEMORY_SCOPE_VALUES, "ck_cpsp_global_scope"),
        ck("cross_companion_private_read_policy", CROSS_PRIVATE_READ_POLICY_VALUES, "ck_cpsp_cross_read"),
        ck("private_to_shared_policy", MEMORY_SYNC_POLICY_VALUES, "ck_cpsp_private_to_shared"),
        ck("shared_to_private_policy", MEMORY_SYNC_POLICY_VALUES, "ck_cpsp_shared_to_private"),
        sa.CheckConstraint(
            "(allow_observing_companion_long_term_memory = true OR default_observing_memory_participation = 'none')",
            name="ck_cpsp_observer_default",
        ),
    )
    op.create_index("idx_cpsp_session_status", "co_presence_session_policies", ["co_presence_session_id", "policy_status"])

    op.create_table(
        "participant_awareness_states",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=False),
        sa.Column("participant_id", postgresql.UUID, nullable=False),
        sa.Column("target_participant_id", postgresql.UUID, nullable=True),
        sa.Column("awareness_type", sa.Text(), nullable=False, server_default=sa.text("'participant_presence'")),
        sa.Column("awareness_level", sa.Text(), nullable=False, server_default=sa.text("'full'")),
        sa.Column("awareness_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("updated_by_source", sa.Text(), nullable=False, server_default=sa.text("'system'")),
        sa.Column("awareness_summary", sa.Text(), nullable=True),
        sa.Column("awareness_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["participant_id"], ["co_presence_participants.id"]),
        sa.ForeignKeyConstraint(["target_participant_id"], ["co_presence_participants.id"]),
        ck("awareness_type", AWARENESS_TYPE_VALUES, "ck_pas_type"),
        ck("awareness_level", AWARENESS_LEVEL_VALUES, "ck_pas_level"),
        ck("awareness_status", AWARENESS_STATUS_VALUES, "ck_pas_status"),
        ck("updated_by_source", AWARENESS_SOURCE_VALUES, "ck_pas_updated_by"),
    )
    op.create_index(
        "idx_pas_session_participant",
        "participant_awareness_states",
        ["co_presence_session_id", "participant_id", "awareness_type"],
    )

    op.create_table(
        "shared_scenes",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=True),
        sa.Column("owner_companion_id", postgresql.UUID, nullable=True),
        sa.Column("scene_title", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("scene_summary", sa.Text(), nullable=True),
        sa.Column("scene_type", sa.Text(), nullable=False, server_default=sa.text("'conversation'")),
        sa.Column("scene_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("source_type", sa.Text(), nullable=False, server_default=sa.text("'co_presence_session'")),
        sa.Column("focal_topic", sa.Text(), nullable=True),
        sa.Column("visibility_scope", sa.Text(), nullable=False, server_default=sa.text("'role_summary'")),
        sa.Column("context_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column(
            "visibility_policy_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["owner_companion_id"], ["companions.id"]),
        ck("scene_type", SCENE_TYPE_VALUES, "ck_ss_type"),
        ck("scene_status", SCENE_STATUS_VALUES, "ck_ss_status"),
        ck("source_type", SCENE_SOURCE_VALUES, "ck_ss_source"),
        ck("visibility_scope", VISIBILITY_SCOPE_VALUES, "ck_ss_visibility"),
    )
    op.create_index("idx_ss_session_status", "shared_scenes", ["co_presence_session_id", "scene_status", "opened_at"])

    op.create_table(
        "shared_scene_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("shared_scene_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=True),
        sa.Column("participant_id", postgresql.UUID, nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False, server_default=sa.text("'scene_note'")),
        sa.Column("event_source", sa.Text(), nullable=False, server_default=sa.text("'system'")),
        sa.Column("title", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("visibility_scope", sa.Text(), nullable=False, server_default=sa.text("'role_summary'")),
        sa.Column(
            "triggers_shared_experience_candidate",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("event_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["shared_scene_id"], ["shared_scenes.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["participant_id"], ["co_presence_participants.id"]),
        ck("event_type", SCENE_EVENT_TYPE_VALUES, "ck_sse_type"),
        ck("event_source", SCENE_EVENT_SOURCE_VALUES, "ck_sse_source"),
        ck("visibility_scope", VISIBILITY_SCOPE_VALUES, "ck_sse_visibility"),
    )
    op.create_index("idx_sse_scene_occurred", "shared_scene_events", ["shared_scene_id", "occurred_at"])

    op.create_table(
        "shared_experience_records",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=True),
        sa.Column("shared_scene_id", postgresql.UUID, nullable=True),
        sa.Column("source_scene_event_id", postgresql.UUID, nullable=True),
        sa.Column("source_conversation_id", postgresql.UUID, nullable=True),
        sa.Column("source_trace_run_id", postgresql.UUID, nullable=True),
        sa.Column("source_type", sa.Text(), nullable=False, server_default=sa.text("'session'")),
        sa.Column("experience_title", sa.Text(), nullable=True),
        sa.Column("experience_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("experience_detail", sa.Text(), nullable=True),
        sa.Column("experience_status", sa.Text(), nullable=False, server_default=sa.text("'captured'")),
        sa.Column(
            "recommended_memory_action",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'shared_candidate'"),
        ),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_participant_id", postgresql.UUID, nullable=True),
        sa.Column("approved_shared_memory_id", postgresql.UUID, nullable=True),
        sa.Column("policy_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["shared_scene_id"], ["shared_scenes.id"]),
        sa.ForeignKeyConstraint(["source_scene_event_id"], ["shared_scene_events.id"]),
        sa.ForeignKeyConstraint(["source_conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["source_trace_run_id"], ["trace_runs.id"]),
        sa.ForeignKeyConstraint(["created_by_participant_id"], ["co_presence_participants.id"]),
        sa.ForeignKeyConstraint(["approved_shared_memory_id"], ["shared_episodic_memories.id"]),
        ck("source_type", EXPERIENCE_SOURCE_VALUES, "ck_ser_source"),
        ck("experience_status", EXPERIENCE_STATUS_VALUES, "ck_ser_status"),
        ck("recommended_memory_action", EXPERIENCE_MEMORY_ACTION_VALUES, "ck_ser_memory_action"),
        sa.CheckConstraint(
            "("
            "co_presence_session_id IS NOT NULL "
            "OR shared_scene_id IS NOT NULL "
            "OR source_scene_event_id IS NOT NULL "
            "OR source_conversation_id IS NOT NULL "
            "OR source_trace_run_id IS NOT NULL"
            ")",
            name="ck_ser_source_ref",
        ),
    )
    op.create_index(
        "idx_ser_session_status",
        "shared_experience_records",
        ["co_presence_session_id", "experience_status", "occurred_at"],
    )

    op.create_table(
        "participant_memory_permissions",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=False),
        sa.Column("participant_id", postgresql.UUID, nullable=False),
        sa.Column("permission_source", sa.Text(), nullable=False, server_default=sa.text("'session_default'")),
        sa.Column("memory_participation_override", sa.Text(), nullable=True),
        sa.Column("allow_private_candidate", sa.Boolean(), nullable=True),
        sa.Column("allow_shared_candidate", sa.Boolean(), nullable=True),
        sa.Column("allow_user_global_summary_read", sa.Boolean(), nullable=True),
        sa.Column("allow_user_global_full_read", sa.Boolean(), nullable=True),
        sa.Column("allow_cross_companion_private_read", sa.Boolean(), nullable=True),
        sa.Column("allow_private_to_shared_sync", sa.Boolean(), nullable=True),
        sa.Column("allow_shared_to_private_sync", sa.Boolean(), nullable=True),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("boundary_policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["participant_id"], ["co_presence_participants.id"]),
        sa.UniqueConstraint("co_presence_session_id", "participant_id", name="uq_pmp_session_participant"),
        ck("permission_source", PERMISSION_SOURCE_VALUES, "ck_pmp_source"),
        sa.CheckConstraint(
            "(memory_participation_override IS NULL OR memory_participation_override IN ('none', 'working_memory_only', 'candidate_only', 'shared_candidate_allowed', 'private_candidate_allowed'))",
            name="ck_pmp_participation",
        ),
    )
    op.create_index(
        "idx_pmp_session_participant",
        "participant_memory_permissions",
        ["co_presence_session_id", "participant_id"],
    )

    op.add_column("conversations", sa.Column("co_presence_session_id", postgresql.UUID, nullable=True))
    op.add_column("conversations", sa.Column("shared_scene_id", postgresql.UUID, nullable=True))
    op.create_foreign_key(
        "fk_conversations_co_presence_session_id",
        "conversations",
        "co_presence_sessions",
        ["co_presence_session_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_conversations_shared_scene_id",
        "conversations",
        "shared_scenes",
        ["shared_scene_id"],
        ["id"],
    )
    op.create_index("idx_conversations_co_presence", "conversations", ["co_presence_session_id"])
    op.create_index("idx_conversations_shared_scene", "conversations", ["shared_scene_id"])

    op.add_column("continuity_snapshots", sa.Column("co_presence_session_id", postgresql.UUID, nullable=True))
    op.add_column("continuity_snapshots", sa.Column("shared_scene_id", postgresql.UUID, nullable=True))
    op.add_column(
        "continuity_snapshots",
        sa.Column(
            "participant_awareness_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_foreign_key(
        "fk_continuity_snapshots_co_presence_session_id",
        "continuity_snapshots",
        "co_presence_sessions",
        ["co_presence_session_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_continuity_snapshots_shared_scene_id",
        "continuity_snapshots",
        "shared_scenes",
        ["shared_scene_id"],
        ["id"],
    )
    op.create_index("idx_continuity_snapshots_co_presence", "continuity_snapshots", ["co_presence_session_id"])
    op.create_index("idx_continuity_snapshots_shared_scene", "continuity_snapshots", ["shared_scene_id"])

    op.add_column("shared_memory_candidates", sa.Column("source_shared_experience_record_id", postgresql.UUID, nullable=True))
    op.create_foreign_key(
        "fk_shared_memory_candidates_source_shared_experience_record_id",
        "shared_memory_candidates",
        "shared_experience_records",
        ["source_shared_experience_record_id"],
        ["id"],
    )
    op.create_index(
        "idx_smc_shared_experience",
        "shared_memory_candidates",
        ["source_shared_experience_record_id"],
    )


def downgrade() -> None:
    op.alter_column("memory_candidates", "proposed_owner_companion_id", nullable=True)
    op.alter_column("memories", "owner_companion_id", nullable=True)
    op.execute("DROP TRIGGER IF EXISTS trg_phase4_memory_candidates_owner_defaults ON memory_candidates")
    op.execute("DROP FUNCTION IF EXISTS phase4_set_memory_candidate_owner_defaults()")
    op.execute("DROP TRIGGER IF EXISTS trg_phase4_memories_owner_defaults ON memories")
    op.execute("DROP FUNCTION IF EXISTS phase4_set_memory_owner_defaults()")

    op.drop_index("idx_smc_shared_experience", table_name="shared_memory_candidates")
    op.drop_constraint(
        "fk_shared_memory_candidates_source_shared_experience_record_id",
        "shared_memory_candidates",
        type_="foreignkey",
    )
    op.drop_column("shared_memory_candidates", "source_shared_experience_record_id")

    op.drop_index("idx_continuity_snapshots_shared_scene", table_name="continuity_snapshots")
    op.drop_index("idx_continuity_snapshots_co_presence", table_name="continuity_snapshots")
    op.drop_constraint(
        "fk_continuity_snapshots_shared_scene_id",
        "continuity_snapshots",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_continuity_snapshots_co_presence_session_id",
        "continuity_snapshots",
        type_="foreignkey",
    )
    op.drop_column("continuity_snapshots", "participant_awareness_json")
    op.drop_column("continuity_snapshots", "shared_scene_id")
    op.drop_column("continuity_snapshots", "co_presence_session_id")

    op.drop_index("idx_conversations_shared_scene", table_name="conversations")
    op.drop_index("idx_conversations_co_presence", table_name="conversations")
    op.drop_constraint("fk_conversations_shared_scene_id", "conversations", type_="foreignkey")
    op.drop_constraint("fk_conversations_co_presence_session_id", "conversations", type_="foreignkey")
    op.drop_column("conversations", "shared_scene_id")
    op.drop_column("conversations", "co_presence_session_id")

    op.drop_index("idx_pmp_session_participant", table_name="participant_memory_permissions")
    op.drop_table("participant_memory_permissions")

    op.drop_index("idx_ser_session_status", table_name="shared_experience_records")
    op.drop_table("shared_experience_records")

    op.drop_index("idx_sse_scene_occurred", table_name="shared_scene_events")
    op.drop_table("shared_scene_events")

    op.drop_index("idx_ss_session_status", table_name="shared_scenes")
    op.drop_table("shared_scenes")

    op.drop_index("idx_pas_session_participant", table_name="participant_awareness_states")
    op.drop_table("participant_awareness_states")

    op.drop_index("idx_cpsp_session_status", table_name="co_presence_session_policies")
    op.drop_table("co_presence_session_policies")

    op.drop_index("idx_copp_session_role", table_name="co_presence_participants")
    op.drop_table("co_presence_participants")

    op.drop_index("idx_cps_primary_companion_status", table_name="co_presence_sessions")
    op.drop_index("idx_cps_user_status", table_name="co_presence_sessions")
    op.drop_table("co_presence_sessions")
