"""phase5_05_resident_presence_hard_stop_schema

Revision ID: p5_05_resident_presence
Revises: p5_04_realtime_memory
Create Date: 2026-06-02 00:00:00.000000

Create Phase 5 Reoriented resident presence, presence budget, quiet/focus
mode, co-presence invitation, and scoped hard stop schema. R5 remains
schema-only: no desktop resident app, mobile resident app, real notification
integration, API implementation, service logic, or frontend implementation.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p5_05_resident_presence"
down_revision: Union[str, Sequence[str], None] = "p5_04_realtime_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


RESIDENT_STATUS_VALUES = ("available", "quiet", "focus", "sleep", "paused", "hard_stopped")
STATUS_SOURCE_VALUES = ("user", "system", "schedule", "boundary_policy")
INTERRUPTION_LEVEL_VALUES = ("none", "low", "medium", "high")
PRESENCE_BUDGET_SCOPE_VALUES = ("day", "week", "session", "channel")
BUDGET_STATUS_VALUES = ("active", "paused", "exhausted", "archived")
BUDGET_ENFORCEMENT_VALUES = ("queue_when_exhausted", "hard_stop_when_exhausted", "notify_only")
INVITATION_STATUS_VALUES = ("queued", "pending_review", "accepted", "rejected", "expired", "cancelled")
INVITATION_SOURCE_VALUES = ("user_request", "companion_suggestion", "system")
QUIET_STATUS_VALUES = ("active", "paused", "archived")
QUIET_POLICY_VALUES = ("block", "queue", "low_priority")
FOCUS_STATUS_VALUES = ("started", "ended", "paused", "cancelled")
FOCUS_SCOPE_VALUES = ("session", "channel", "companion", "all_realtime")
RESIDENT_EVENT_TYPE_VALUES = ("nudge", "invitation", "ambient_status", "boundary_notice", "hard_stop_notice")
RESIDENT_EVENT_STATUS_VALUES = ("queued", "delivered", "suppressed", "cancelled")
HARD_STOP_SCOPE_VALUES = ("session", "channel", "companion", "sensor", "all_realtime")
HARD_STOP_STATUS_VALUES = ("active", "released", "expired", "archived")
HARD_STOP_SOURCE_VALUES = ("user", "boundary_policy", "system")
HARD_STOP_AUDIT_TYPE_VALUES = ("created", "enforced", "released", "violation_detected", "expired")
AUDIT_STATUS_VALUES = ("recorded", "review_required", "resolved")


def ck(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=name)


def jsonb_default() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "companion_resident_status_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=True),
        sa.Column("status_type", sa.Text(), nullable=False, server_default=sa.text("'available'")),
        sa.Column("status_source", sa.Text(), nullable=False, server_default=sa.text("'system'")),
        sa.Column("interruption_level", sa.Text(), nullable=False, server_default=sa.text("'low'")),
        sa.Column("allows_unsolicited_presence", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("presence_summary", sa.Text(), nullable=True),
        sa.Column("policy_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        ck("status_type", RESIDENT_STATUS_VALUES, "ck_crse_status"),
        ck("status_source", STATUS_SOURCE_VALUES, "ck_crse_source"),
        ck("interruption_level", INTERRUPTION_LEVEL_VALUES, "ck_crse_interruption"),
        sa.CheckConstraint(
            "allows_unsolicited_presence = false OR interruption_level IN ('none', 'low')",
            name="ck_crse_low_unsolicited",
        ),
    )
    op.create_index("idx_crse_companion_occurred", "companion_resident_status_events", ["companion_id", "occurred_at"])
    op.create_index("idx_crse_realtime_status", "companion_resident_status_events", ["realtime_session_id", "status_type"])

    op.create_table(
        "companion_presence_budgets",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("budget_scope", sa.Text(), nullable=False, server_default=sa.text("'day'")),
        sa.Column("budget_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("enforcement_policy", sa.Text(), nullable=False, server_default=sa.text("'queue_when_exhausted'")),
        sa.Column("max_presence_minutes", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.Column("used_presence_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("max_interruptions", sa.Integer(), nullable=False, server_default=sa.text("3")),
        sa.Column("used_interruptions", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("window_starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("budget_policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        ck("budget_scope", PRESENCE_BUDGET_SCOPE_VALUES, "ck_cpb_scope"),
        ck("budget_status", BUDGET_STATUS_VALUES, "ck_cpb_status"),
        ck("enforcement_policy", BUDGET_ENFORCEMENT_VALUES, "ck_cpb_enforcement"),
        sa.CheckConstraint("max_presence_minutes >= 0 AND used_presence_minutes >= 0", name="ck_cpb_minutes_nonnegative"),
        sa.CheckConstraint("used_presence_minutes <= max_presence_minutes", name="ck_cpb_minutes_within_budget"),
        sa.CheckConstraint("max_interruptions >= 0 AND used_interruptions >= 0", name="ck_cpb_interruptions_nonnegative"),
        sa.CheckConstraint("used_interruptions <= max_interruptions", name="ck_cpb_interruptions_within_budget"),
    )
    op.create_index("idx_cpb_companion_scope", "companion_presence_budgets", ["companion_id", "budget_scope", "budget_status"])

    op.create_table(
        "copresence_invitations",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=True),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=True),
        sa.Column("inviter_companion_id", postgresql.UUID, nullable=True),
        sa.Column("target_companion_id", postgresql.UUID, nullable=True),
        sa.Column("invitation_status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("invitation_source", sa.Text(), nullable=False, server_default=sa.text("'companion_suggestion'")),
        sa.Column("requires_user_approval", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_join_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("memory_candidate_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("invitation_reason", sa.Text(), nullable=True),
        sa.Column("policy_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["inviter_companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["target_companion_id"], ["companions.id"]),
        ck("invitation_status", INVITATION_STATUS_VALUES, "ck_cpi_status"),
        ck("invitation_source", INVITATION_SOURCE_VALUES, "ck_cpi_source"),
        sa.CheckConstraint("requires_user_approval = true", name="ck_cpi_review_required"),
        sa.CheckConstraint("auto_join_allowed = false", name="ck_cpi_no_auto_join"),
        sa.CheckConstraint("memory_candidate_allowed = false", name="ck_cpi_no_default_memory_candidate"),
    )
    op.create_index("idx_cpi_realtime_status", "copresence_invitations", ["realtime_session_id", "invitation_status"])
    op.create_index("idx_cpi_target_status", "copresence_invitations", ["target_companion_id", "invitation_status"])

    op.create_table(
        "quiet_hour_settings",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=True),
        sa.Column("quiet_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("quiet_policy", sa.Text(), nullable=False, server_default=sa.text("'queue'")),
        sa.Column("day_of_week", sa.Integer(), nullable=True),
        sa.Column("start_minute", sa.Integer(), nullable=False),
        sa.Column("end_minute", sa.Integer(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False, server_default=sa.text("'UTC'")),
        sa.Column("allows_emergency_override", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        ck("quiet_status", QUIET_STATUS_VALUES, "ck_qhs_status"),
        ck("quiet_policy", QUIET_POLICY_VALUES, "ck_qhs_policy"),
        sa.CheckConstraint("day_of_week IS NULL OR day_of_week BETWEEN 0 AND 6", name="ck_qhs_day"),
        sa.CheckConstraint("start_minute BETWEEN 0 AND 1439", name="ck_qhs_start_minute"),
        sa.CheckConstraint("end_minute BETWEEN 0 AND 1439", name="ck_qhs_end_minute"),
    )
    op.create_index("idx_qhs_user_status", "quiet_hour_settings", ["user_id", "quiet_status"])
    op.create_index("idx_qhs_companion_status", "quiet_hour_settings", ["companion_id", "quiet_status"])

    op.create_table(
        "focus_mode_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=True),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=True),
        sa.Column("focus_status", sa.Text(), nullable=False, server_default=sa.text("'started'")),
        sa.Column("focus_scope", sa.Text(), nullable=False, server_default=sa.text("'all_realtime'")),
        sa.Column("suppress_presence", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("suppress_notifications", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_critical_only", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        ck("focus_status", FOCUS_STATUS_VALUES, "ck_fme_status"),
        ck("focus_scope", FOCUS_SCOPE_VALUES, "ck_fme_scope"),
        sa.CheckConstraint(
            "focus_status <> 'started' OR (suppress_presence = true AND suppress_notifications = true)",
            name="ck_fme_started_suppresses",
        ),
    )
    op.create_index("idx_fme_user_status", "focus_mode_events", ["user_id", "focus_status", "started_at"])
    op.create_index("idx_fme_realtime_status", "focus_mode_events", ["realtime_session_id", "focus_status"])

    op.create_table(
        "resident_presence_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False, server_default=sa.text("'ambient_status'")),
        sa.Column("event_status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("interruption_level", sa.Text(), nullable=False, server_default=sa.text("'low'")),
        sa.Column("requires_user_confirmation", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("delivery_surface", sa.Text(), nullable=False, server_default=sa.text("'app_page'")),
        sa.Column("event_summary", sa.Text(), nullable=True),
        sa.Column("policy_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        ck("event_type", RESIDENT_EVENT_TYPE_VALUES, "ck_rpe_type"),
        ck("event_status", RESIDENT_EVENT_STATUS_VALUES, "ck_rpe_status"),
        ck("interruption_level", INTERRUPTION_LEVEL_VALUES, "ck_rpe_interruption"),
        sa.CheckConstraint(
            "interruption_level IN ('none', 'low') OR requires_user_confirmation = true",
            name="ck_rpe_high_requires_confirmation",
        ),
    )
    op.create_index("idx_rpe_companion_status", "resident_presence_events", ["companion_id", "event_status", "occurred_at"])
    op.create_index("idx_rpe_realtime_type", "resident_presence_events", ["realtime_session_id", "event_type"])

    op.create_table(
        "scoped_hard_stop_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("hard_stop_scope", sa.Text(), nullable=False),
        sa.Column("hard_stop_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("initiated_by", sa.Text(), nullable=False, server_default=sa.text("'user'")),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=True),
        sa.Column("channel_id", postgresql.UUID, nullable=True),
        sa.Column("companion_id", postgresql.UUID, nullable=True),
        sa.Column("context_event_id", postgresql.UUID, nullable=True),
        sa.Column("stop_reason", sa.Text(), nullable=True),
        sa.Column("stops_listening", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("stops_speaking", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("stops_observing", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("stops_memory_capture", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("stops_context_capture", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("requires_audit", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("policy_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["channel_id"], ["realtime_session_channels.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["context_event_id"], ["multimodal_context_events.id"]),
        ck("hard_stop_scope", HARD_STOP_SCOPE_VALUES, "ck_shse_scope"),
        ck("hard_stop_status", HARD_STOP_STATUS_VALUES, "ck_shse_status"),
        ck("initiated_by", HARD_STOP_SOURCE_VALUES, "ck_shse_source"),
        sa.CheckConstraint(
            "("
            "(hard_stop_scope = 'session' AND realtime_session_id IS NOT NULL)"
            " OR (hard_stop_scope = 'channel' AND channel_id IS NOT NULL)"
            " OR (hard_stop_scope = 'companion' AND companion_id IS NOT NULL)"
            " OR (hard_stop_scope = 'sensor' AND context_event_id IS NOT NULL)"
            " OR hard_stop_scope = 'all_realtime'"
            ")",
            name="ck_shse_scope_target",
        ),
        sa.CheckConstraint("requires_audit = true", name="ck_shse_requires_audit"),
        sa.CheckConstraint(
            "stops_listening = true OR stops_speaking = true OR stops_observing = true OR "
            "stops_memory_capture = true OR stops_context_capture = true",
            name="ck_shse_stops_something",
        ),
    )
    op.create_index("idx_shse_user_scope_status", "scoped_hard_stop_events", ["user_id", "hard_stop_scope", "hard_stop_status"])
    op.create_index("idx_shse_realtime_status", "scoped_hard_stop_events", ["realtime_session_id", "hard_stop_status"])
    op.create_index("idx_shse_companion_status", "scoped_hard_stop_events", ["companion_id", "hard_stop_status"])

    op.create_table(
        "hard_stop_audit_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("hard_stop_event_id", postgresql.UUID, nullable=False),
        sa.Column("audit_event_type", sa.Text(), nullable=False, server_default=sa.text("'created'")),
        sa.Column("audit_status", sa.Text(), nullable=False, server_default=sa.text("'recorded'")),
        sa.Column("affected_scope", sa.Text(), nullable=False),
        sa.Column("affected_participant_id", postgresql.UUID, nullable=True),
        sa.Column("audit_summary", sa.Text(), nullable=True),
        sa.Column("audit_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["hard_stop_event_id"], ["scoped_hard_stop_events.id"]),
        sa.ForeignKeyConstraint(["affected_participant_id"], ["realtime_copresence_participants.id"]),
        ck("audit_event_type", HARD_STOP_AUDIT_TYPE_VALUES, "ck_hsae_type"),
        ck("audit_status", AUDIT_STATUS_VALUES, "ck_hsae_status"),
        ck("affected_scope", HARD_STOP_SCOPE_VALUES, "ck_hsae_scope"),
    )
    op.create_index("idx_hsae_hard_stop_type", "hard_stop_audit_events", ["hard_stop_event_id", "audit_event_type", "occurred_at"])


def downgrade() -> None:
    op.drop_index("idx_hsae_hard_stop_type", table_name="hard_stop_audit_events")
    op.drop_table("hard_stop_audit_events")

    op.drop_index("idx_shse_companion_status", table_name="scoped_hard_stop_events")
    op.drop_index("idx_shse_realtime_status", table_name="scoped_hard_stop_events")
    op.drop_index("idx_shse_user_scope_status", table_name="scoped_hard_stop_events")
    op.drop_table("scoped_hard_stop_events")

    op.drop_index("idx_rpe_realtime_type", table_name="resident_presence_events")
    op.drop_index("idx_rpe_companion_status", table_name="resident_presence_events")
    op.drop_table("resident_presence_events")

    op.drop_index("idx_fme_realtime_status", table_name="focus_mode_events")
    op.drop_index("idx_fme_user_status", table_name="focus_mode_events")
    op.drop_table("focus_mode_events")

    op.drop_index("idx_qhs_companion_status", table_name="quiet_hour_settings")
    op.drop_index("idx_qhs_user_status", table_name="quiet_hour_settings")
    op.drop_table("quiet_hour_settings")

    op.drop_index("idx_cpi_target_status", table_name="copresence_invitations")
    op.drop_index("idx_cpi_realtime_status", table_name="copresence_invitations")
    op.drop_table("copresence_invitations")

    op.drop_index("idx_cpb_companion_scope", table_name="companion_presence_budgets")
    op.drop_table("companion_presence_budgets")

    op.drop_index("idx_crse_realtime_status", table_name="companion_resident_status_events")
    op.drop_index("idx_crse_companion_occurred", table_name="companion_resident_status_events")
    op.drop_table("companion_resident_status_events")
