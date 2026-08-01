"""phase6_05_channel_presence_policy_schema

Revision ID: p6_05_channel_presence
Revises: p6_04_channel_memory
Create Date: 2026-06-03 00:00:00.000000

Create Phase 6 Channel Presence Policy / Check-in / Quiet / Focus / Budget
schema. External channel presence defaults to reply-only; proactive check-ins
must be user-enabled and constrained by quiet hours, focus mode, presence
budget, and meaningful silence.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p6_05_channel_presence"
down_revision: Union[str, Sequence[str], None] = "p6_04_channel_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


POLICY_STATUS_VALUES = ("draft", "active", "disabled", "revoked")
PRESENCE_MODE_VALUES = ("reply_only", "low_frequency_checkin")
CHECKIN_FREQUENCY_VALUES = ("manual", "daily", "weekly", "monthly")
BUDGET_EVENT_TYPE_VALUES = ("allocated", "consumed", "suppressed", "refunded", "reset")
FOCUS_STATUS_VALUES = ("active", "inactive")
SILENCE_REASON_VALUES = ("low_salience", "recent_user_activity", "relationship_boundary", "cooldown", "manual")
SUPPRESSION_REASON_VALUES = ("quiet_hours", "focus_mode", "presence_budget", "meaningful_silence", "revoked", "muted", "outbound_disabled")
SUPPRESSION_STATUS_VALUES = ("applied", "overridden_by_user", "expired")


def ck(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=name)


def jsonb_default() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "channel_presence_policies",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("channel_binding_id", postgresql.UUID, nullable=False),
        sa.Column("provider_id", postgresql.UUID, nullable=False),
        sa.Column("provider_bot_id", postgresql.UUID, nullable=True),
        sa.Column("policy_status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("presence_mode", sa.Text(), nullable=False, server_default=sa.text("'reply_only'")),
        sa.Column("reply_only_default", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("low_frequency_checkin_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("channel_mute", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("outbound_disabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("daily_presence_budget", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("remaining_presence_budget", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("quiet_hours_enforced", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("focus_mode_enforced", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("meaningful_silence_enforced", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["channel_binding_id"], ["channel_bindings.id"]),
        sa.ForeignKeyConstraint(["provider_id"], ["channel_providers.id"]),
        sa.ForeignKeyConstraint(["provider_bot_id"], ["channel_bot_registries.id"]),
        ck("policy_status", POLICY_STATUS_VALUES, "ck_channel_presence_policies_status"),
        ck("presence_mode", PRESENCE_MODE_VALUES, "ck_channel_presence_policies_mode"),
        sa.CheckConstraint("reply_only_default = true", name="ck_channel_presence_policies_reply_only_default"),
        sa.CheckConstraint(
            "low_frequency_checkin_enabled = false OR presence_mode = 'low_frequency_checkin'",
            name="ck_channel_presence_policies_checkin_requires_mode",
        ),
        sa.CheckConstraint("daily_presence_budget >= 0", name="ck_channel_presence_policies_daily_budget_nonnegative"),
        sa.CheckConstraint("remaining_presence_budget >= 0", name="ck_channel_presence_policies_remaining_budget_nonnegative"),
        sa.CheckConstraint("quiet_hours_enforced = true", name="ck_channel_presence_policies_quiet_enforced"),
        sa.CheckConstraint("focus_mode_enforced = true", name="ck_channel_presence_policies_focus_enforced"),
        sa.CheckConstraint("meaningful_silence_enforced = true", name="ck_channel_presence_policies_silence_enforced"),
    )
    op.create_index("idx_channel_presence_policies_binding_status", "channel_presence_policies", ["channel_binding_id", "policy_status"])
    op.create_index("idx_channel_presence_policies_companion_status", "channel_presence_policies", ["companion_id", "policy_status"])

    op.create_table(
        "channel_checkin_settings",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("channel_presence_policy_id", postgresql.UUID, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("frequency", sa.Text(), nullable=False, server_default=sa.text("'manual'")),
        sa.Column("min_interval_seconds", sa.Integer(), nullable=False, server_default=sa.text("86400")),
        sa.Column("requires_user_opt_in", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("quiet_hours_enforced", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("focus_mode_enforced", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("presence_budget_enforced", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("meaningful_silence_enforced", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("next_eligible_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["channel_presence_policy_id"], ["channel_presence_policies.id"]),
        ck("frequency", CHECKIN_FREQUENCY_VALUES, "ck_channel_checkin_settings_frequency"),
        sa.CheckConstraint("min_interval_seconds >= 0", name="ck_channel_checkin_settings_interval_nonnegative"),
        sa.CheckConstraint("requires_user_opt_in = true", name="ck_channel_checkin_settings_user_opt_in"),
        sa.CheckConstraint("quiet_hours_enforced = true", name="ck_channel_checkin_settings_quiet_enforced"),
        sa.CheckConstraint("focus_mode_enforced = true", name="ck_channel_checkin_settings_focus_enforced"),
        sa.CheckConstraint("presence_budget_enforced = true", name="ck_channel_checkin_settings_budget_enforced"),
        sa.CheckConstraint("meaningful_silence_enforced = true", name="ck_channel_checkin_settings_silence_enforced"),
    )
    op.create_index("idx_channel_checkin_settings_policy", "channel_checkin_settings", ["channel_presence_policy_id"])

    op.create_table(
        "channel_presence_budget_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("channel_presence_policy_id", postgresql.UUID, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("budget_delta", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("remaining_budget", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("event_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("event_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["channel_presence_policy_id"], ["channel_presence_policies.id"]),
        ck("event_type", BUDGET_EVENT_TYPE_VALUES, "ck_channel_presence_budget_events_type"),
        sa.CheckConstraint("remaining_budget >= 0", name="ck_channel_presence_budget_events_remaining_nonnegative"),
    )
    op.create_index("idx_channel_presence_budget_events_policy_time", "channel_presence_budget_events", ["channel_presence_policy_id", "occurred_at"])

    op.create_table(
        "channel_quiet_hour_rules",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("channel_presence_policy_id", postgresql.UUID, nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("timezone", sa.Text(), nullable=False, server_default=sa.text("'UTC'")),
        sa.Column("start_minute_of_day", sa.Integer(), nullable=False),
        sa.Column("end_minute_of_day", sa.Integer(), nullable=False),
        sa.Column("applies_to_checkins", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("applies_to_outbound", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["channel_presence_policy_id"], ["channel_presence_policies.id"]),
        sa.CheckConstraint("start_minute_of_day >= 0 AND start_minute_of_day < 1440", name="ck_channel_quiet_hour_rules_start"),
        sa.CheckConstraint("end_minute_of_day >= 0 AND end_minute_of_day < 1440", name="ck_channel_quiet_hour_rules_end"),
        sa.CheckConstraint("applies_to_checkins = true", name="ck_channel_quiet_hour_rules_checkins"),
        sa.CheckConstraint("applies_to_outbound = true", name="ck_channel_quiet_hour_rules_outbound"),
    )
    op.create_index("idx_channel_quiet_hour_rules_policy", "channel_quiet_hour_rules", ["channel_presence_policy_id"])

    op.create_table(
        "channel_focus_mode_rules",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("channel_presence_policy_id", postgresql.UUID, nullable=False),
        sa.Column("focus_status", sa.Text(), nullable=False, server_default=sa.text("'inactive'")),
        sa.Column("suppresses_outbound", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("suppresses_checkins", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("focus_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["channel_presence_policy_id"], ["channel_presence_policies.id"]),
        ck("focus_status", FOCUS_STATUS_VALUES, "ck_channel_focus_mode_rules_status"),
        sa.CheckConstraint("suppresses_outbound = true", name="ck_channel_focus_mode_rules_outbound"),
        sa.CheckConstraint("suppresses_checkins = true", name="ck_channel_focus_mode_rules_checkins"),
    )
    op.create_index("idx_channel_focus_mode_rules_policy_status", "channel_focus_mode_rules", ["channel_presence_policy_id", "focus_status"])

    op.create_table(
        "channel_meaningful_silence_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("channel_presence_policy_id", postgresql.UUID, nullable=False),
        sa.Column("silence_reason", sa.Text(), nullable=False),
        sa.Column("suppressed_outbound_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("silence_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("event_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["channel_presence_policy_id"], ["channel_presence_policies.id"]),
        ck("silence_reason", SILENCE_REASON_VALUES, "ck_channel_meaningful_silence_events_reason"),
        sa.CheckConstraint("suppressed_outbound_count >= 0", name="ck_channel_meaningful_silence_events_count"),
    )
    op.create_index("idx_channel_meaningful_silence_events_policy_time", "channel_meaningful_silence_events", ["channel_presence_policy_id", "occurred_at"])

    op.create_table(
        "channel_outbound_suppression_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("channel_presence_policy_id", postgresql.UUID, nullable=False),
        sa.Column("channel_delivery_event_id", postgresql.UUID, nullable=True),
        sa.Column("suppression_reason", sa.Text(), nullable=False),
        sa.Column("suppression_status", sa.Text(), nullable=False, server_default=sa.text("'applied'")),
        sa.Column("suppression_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("safe_suppression_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["channel_presence_policy_id"], ["channel_presence_policies.id"]),
        sa.ForeignKeyConstraint(["channel_delivery_event_id"], ["channel_delivery_events.id"]),
        ck("suppression_reason", SUPPRESSION_REASON_VALUES, "ck_channel_outbound_suppression_events_reason"),
        ck("suppression_status", SUPPRESSION_STATUS_VALUES, "ck_channel_outbound_suppression_events_status"),
    )
    op.create_index("idx_channel_outbound_suppression_policy_time", "channel_outbound_suppression_events", ["channel_presence_policy_id", "occurred_at"])
    op.create_index("idx_channel_outbound_suppression_delivery", "channel_outbound_suppression_events", ["channel_delivery_event_id"])


def downgrade() -> None:
    op.drop_index("idx_channel_outbound_suppression_delivery", table_name="channel_outbound_suppression_events")
    op.drop_index("idx_channel_outbound_suppression_policy_time", table_name="channel_outbound_suppression_events")
    op.drop_table("channel_outbound_suppression_events")

    op.drop_index("idx_channel_meaningful_silence_events_policy_time", table_name="channel_meaningful_silence_events")
    op.drop_table("channel_meaningful_silence_events")

    op.drop_index("idx_channel_focus_mode_rules_policy_status", table_name="channel_focus_mode_rules")
    op.drop_table("channel_focus_mode_rules")

    op.drop_index("idx_channel_quiet_hour_rules_policy", table_name="channel_quiet_hour_rules")
    op.drop_table("channel_quiet_hour_rules")

    op.drop_index("idx_channel_presence_budget_events_policy_time", table_name="channel_presence_budget_events")
    op.drop_table("channel_presence_budget_events")

    op.drop_index("idx_channel_checkin_settings_policy", table_name="channel_checkin_settings")
    op.drop_table("channel_checkin_settings")

    op.drop_index("idx_channel_presence_policies_companion_status", table_name="channel_presence_policies")
    op.drop_index("idx_channel_presence_policies_binding_status", table_name="channel_presence_policies")
    op.drop_table("channel_presence_policies")
