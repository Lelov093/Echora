"""Add P5-B1 Room membership and Discord Channel binding foundation.

Revision ID: p5_b1_room_channel_foundation
Revises: p4_b3_dm_binding_guards
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p5_b1_room_channel_foundation"
down_revision = "p4_b3_dm_binding_guards"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("co_presence_sessions", sa.Column("roster_revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("co_presence_participants", sa.Column("rejoined_at", sa.DateTime(timezone=True)))
    op.add_column("co_presence_participants", sa.Column("muted_at", sa.DateTime(timezone=True)))
    op.add_column("co_presence_participants", sa.Column("revoked_at", sa.DateTime(timezone=True)))
    op.add_column("co_presence_participants", sa.Column("membership_revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("companion_channel_identities", sa.Column("revision", sa.Integer(), nullable=False, server_default="1"))

    op.create_check_constraint("ck_p5_room_roster_revision", "co_presence_sessions", "roster_revision >= 1")
    op.create_check_constraint("ck_p5_participant_membership_revision", "co_presence_participants", "membership_revision >= 1")
    op.create_check_constraint("ck_p5_channel_identity_revision", "companion_channel_identities", "revision >= 1")
    op.create_index(
        "uq_p5_active_discord_bot_identity",
        "companion_channel_identities",
        ["provider_bot_id"],
        unique=True,
        postgresql_where=sa.text("provider_bot_id IS NOT NULL AND channel_status = 'active'"),
    )
    op.create_index(
        "uq_p5_active_discord_companion_identity",
        "companion_channel_identities",
        ["companion_id"],
        unique=True,
        postgresql_where=sa.text("provider_bot_id IS NOT NULL AND channel_status = 'active'"),
    )
    op.create_index(
        "uq_p5_room_conversation",
        "conversations",
        ["co_presence_session_id"],
        unique=True,
        postgresql_where=sa.text("co_presence_session_id IS NOT NULL AND deleted_at IS NULL"),
    )

    op.create_table(
        "companion_room_membership_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("co_presence_sessions.id"), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("co_presence_participants.id")),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companions.id"), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("from_status", sa.Text()), sa.Column("to_status", sa.Text()),
        sa.Column("from_role", sa.Text()), sa.Column("to_role", sa.Text()),
        sa.Column("roster_revision", sa.Integer(), nullable=False),
        sa.Column("participant_revision", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("evidence_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("event_type IN ('invited','speaker','observer','muted','inactivated','reactivated','revoked','room_restored')", name="ck_p5_room_membership_event_type"),
        sa.CheckConstraint("roster_revision >= 1 AND participant_revision >= 1", name="ck_p5_room_membership_event_revision"),
    )
    op.create_index("idx_p5_room_membership_events", "companion_room_membership_events", ["co_presence_session_id", "roster_revision", "occurred_at"])

    op.create_table(
        "discord_guilds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("channel_providers.id"), nullable=False),
        sa.Column("provider_guild_ref", sa.Text(), nullable=False),
        sa.Column("provider_guild_ref_hash", sa.String(64), nullable=False),
        sa.Column("guild_display_name", sa.Text(), nullable=False),
        sa.Column("guild_status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("guild_status IN ('active','disabled','revoked')", name="ck_p5_discord_guild_status"),
        sa.CheckConstraint("revision >= 1", name="ck_p5_discord_guild_revision"),
        sa.UniqueConstraint("provider_id", "provider_guild_ref_hash", name="uq_p5_discord_guild_ref"),
    )
    op.create_index("idx_p5_discord_guild_owner", "discord_guilds", ["user_id", "guild_status"])

    op.create_table(
        "discord_text_channels",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("discord_guild_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discord_guilds.id"), nullable=False),
        sa.Column("provider_channel_ref", sa.Text(), nullable=False),
        sa.Column("provider_channel_ref_hash", sa.String(64), nullable=False),
        sa.Column("channel_display_name", sa.Text(), nullable=False),
        sa.Column("channel_status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("permission_status", sa.Text(), nullable=False, server_default="unverified"),
        sa.Column("permission_snapshot_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("channel_status IN ('active','disabled','revoked')", name="ck_p5_discord_channel_status"),
        sa.CheckConstraint("permission_status IN ('unverified','ready','blocked')", name="ck_p5_discord_channel_permission"),
        sa.CheckConstraint("revision >= 1", name="ck_p5_discord_channel_revision"),
        sa.UniqueConstraint("discord_guild_id", "provider_channel_ref_hash", name="uq_p5_discord_channel_ref"),
    )
    op.create_index("idx_p5_discord_channel_owner", "discord_text_channels", ["user_id", "channel_status"])

    op.create_table(
        "discord_channel_room_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("discord_text_channel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discord_text_channels.id"), nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("co_presence_sessions.id"), nullable=False),
        sa.Column("binding_status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("mention_policy", sa.Text(), nullable=False, server_default="mention_only"),
        sa.Column("roster_fingerprint", sa.String(64), nullable=False),
        sa.Column("room_roster_revision", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("paused_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("evidence_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("binding_status IN ('active','paused','conflict_paused','revoked')", name="ck_p5_discord_room_binding_status"),
        sa.CheckConstraint("mention_policy IN ('mention_only','coordinator_managed','observe_only')", name="ck_p5_discord_room_mention_policy"),
        sa.CheckConstraint("room_roster_revision >= 1 AND revision >= 1", name="ck_p5_discord_room_binding_revision"),
    )
    op.create_index("uq_p5_live_channel_room", "discord_channel_room_bindings", ["discord_text_channel_id"], unique=True, postgresql_where=sa.text("binding_status IN ('active','paused','conflict_paused')"))
    op.create_index("uq_p5_live_room_channel", "discord_channel_room_bindings", ["co_presence_session_id"], unique=True, postgresql_where=sa.text("binding_status IN ('active','paused','conflict_paused')"))

    op.create_table(
        "discord_channel_bot_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("discord_text_channel_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discord_text_channels.id"), nullable=False),
        sa.Column("discord_channel_room_binding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discord_channel_room_bindings.id"), nullable=False),
        sa.Column("provider_bot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("channel_bot_registries.id"), nullable=False),
        sa.Column("companion_channel_identity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companion_channel_identities.id"), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companions.id"), nullable=False),
        sa.Column("participation_mode", sa.Text(), nullable=False, server_default="mention_only"),
        sa.Column("membership_status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("identity_revision", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("participation_mode IN ('mention_only','coordinator_managed','observe_only')", name="ck_p5_discord_bot_participation_mode"),
        sa.CheckConstraint("membership_status IN ('active','inactive','revoked')", name="ck_p5_discord_bot_membership_status"),
        sa.CheckConstraint("identity_revision >= 1 AND revision >= 1", name="ck_p5_discord_bot_membership_revision"),
    )
    op.create_index("uq_p5_active_channel_bot", "discord_channel_bot_memberships", ["discord_text_channel_id", "provider_bot_id"], unique=True, postgresql_where=sa.text("membership_status = 'active'"))
    op.create_index("uq_p5_active_channel_companion", "discord_channel_bot_memberships", ["discord_text_channel_id", "companion_id"], unique=True, postgresql_where=sa.text("membership_status = 'active'"))


def downgrade() -> None:
    op.drop_table("discord_channel_bot_memberships")
    op.drop_table("discord_channel_room_bindings")
    op.drop_table("discord_text_channels")
    op.drop_table("discord_guilds")
    op.drop_table("companion_room_membership_events")
    op.drop_index("uq_p5_room_conversation", table_name="conversations")
    op.drop_index("uq_p5_active_discord_companion_identity", table_name="companion_channel_identities")
    op.drop_index("uq_p5_active_discord_bot_identity", table_name="companion_channel_identities")
    op.drop_constraint("ck_p5_channel_identity_revision", "companion_channel_identities", type_="check")
    op.drop_constraint("ck_p5_participant_membership_revision", "co_presence_participants", type_="check")
    op.drop_constraint("ck_p5_room_roster_revision", "co_presence_sessions", type_="check")
    op.drop_column("companion_channel_identities", "revision")
    op.drop_column("co_presence_participants", "membership_revision")
    op.drop_column("co_presence_participants", "revoked_at")
    op.drop_column("co_presence_participants", "muted_at")
    op.drop_column("co_presence_participants", "rejoined_at")
    op.drop_column("co_presence_sessions", "roster_revision")
