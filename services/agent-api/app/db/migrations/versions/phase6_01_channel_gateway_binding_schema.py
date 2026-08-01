"""phase6_01_channel_gateway_binding_schema

Revision ID: p6_01_channel_gateway
Revises: p5_07_channel_gateway
Create Date: 2026-06-03 00:00:00.000000

Create Phase 6 Companion Channel Gateway provider, bot registry, provider
configuration, and binding schema. This is schema-only: no Discord SDK, no
real token handling, no API implementation, and no plaintext token storage.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p6_01_channel_gateway"
down_revision: Union[str, Sequence[str], None] = "p5_07_channel_gateway"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PROVIDER_KIND_VALUES = ("mock", "discord")
PROVIDER_STATUS_VALUES = ("available", "disabled", "deprecated")
CONFIG_STATUS_VALUES = ("draft", "active", "disabled", "revoked")
SECRET_POLICY_VALUES = ("none", "token_secret_ref_only")
BOT_STATUS_VALUES = ("draft", "ready", "disabled", "revoked")
TOKEN_STATUS_VALUES = ("missing", "configured", "revoked", "invalid")
BINDING_STATUS_VALUES = ("draft", "active", "disabled", "revoked")
BINDING_SCOPE_VALUES = ("mock_thread", "dm", "guild_channel")
PERMISSION_SCOPE_VALUES = ("reply_only", "low_frequency_checkin", "manual_outbound_disabled")
OUTBOUND_POLICY_VALUES = ("disabled", "reply_only", "user_approved_only")
MEMORY_POLICY_VALUES = ("ephemeral_only", "ephemeral_review_gated")


def ck(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=name)


def jsonb_default() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "channel_providers",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider_key", sa.Text(), nullable=False),
        sa.Column("provider_display_name", sa.Text(), nullable=False),
        sa.Column("provider_kind", sa.Text(), nullable=False),
        sa.Column("provider_status", sa.Text(), nullable=False, server_default=sa.text("'available'")),
        sa.Column("is_real_provider", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("supports_multi_bot", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("supports_inbound", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("supports_outbound", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("supports_low_frequency_checkin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_external_token", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("config_schema_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_key", name="uq_channel_providers_provider_key"),
        ck("provider_kind", PROVIDER_KIND_VALUES, "ck_channel_providers_kind"),
        ck("provider_status", PROVIDER_STATUS_VALUES, "ck_channel_providers_status"),
        sa.CheckConstraint(
            "provider_kind <> 'discord' OR (is_real_provider = true AND supports_multi_bot = true AND requires_external_token = true)",
            name="ck_channel_providers_discord_real_multibot",
        ),
        sa.CheckConstraint(
            "provider_kind <> 'mock' OR (is_real_provider = false AND requires_external_token = false)",
            name="ck_channel_providers_mock_no_token",
        ),
    )
    op.create_index("idx_channel_providers_kind_status", "channel_providers", ["provider_kind", "provider_status"])

    channel_providers = sa.table(
        "channel_providers",
        sa.column("provider_key", sa.Text()),
        sa.column("provider_display_name", sa.Text()),
        sa.column("provider_kind", sa.Text()),
        sa.column("provider_status", sa.Text()),
        sa.column("is_real_provider", sa.Boolean()),
        sa.column("supports_multi_bot", sa.Boolean()),
        sa.column("supports_inbound", sa.Boolean()),
        sa.column("supports_outbound", sa.Boolean()),
        sa.column("supports_low_frequency_checkin", sa.Boolean()),
        sa.column("requires_external_token", sa.Boolean()),
        sa.column("config_schema_json", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("metadata", postgresql.JSONB(astext_type=sa.Text())),
    )
    op.bulk_insert(
        channel_providers,
        [
            {
                "provider_key": "mock_channel",
                "provider_display_name": "Mock Channel",
                "provider_kind": "mock",
                "provider_status": "available",
                "is_real_provider": False,
                "supports_multi_bot": True,
                "supports_inbound": True,
                "supports_outbound": True,
                "supports_low_frequency_checkin": True,
                "requires_external_token": False,
                "config_schema_json": {},
                "metadata": {"phase": "phase6", "purpose": "contract_validation"},
            },
            {
                "provider_key": "discord",
                "provider_display_name": "Discord",
                "provider_kind": "discord",
                "provider_status": "available",
                "is_real_provider": True,
                "supports_multi_bot": True,
                "supports_inbound": True,
                "supports_outbound": True,
                "supports_low_frequency_checkin": True,
                "requires_external_token": True,
                "config_schema_json": {
                    "token": "token_secret_ref_only",
                    "architecture": "multi_bot_per_companion",
                },
                "metadata": {"phase": "phase6", "first_real_provider": True},
            },
        ],
    )

    op.create_table(
        "channel_provider_configs",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider_id", postgresql.UUID, nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=True),
        sa.Column("config_status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("secret_policy", sa.Text(), nullable=False, server_default=sa.text("'token_secret_ref_only'")),
        sa.Column("stores_plaintext_token", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("provider_config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("safe_public_config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["provider_id"], ["channel_providers.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        ck("config_status", CONFIG_STATUS_VALUES, "ck_channel_provider_configs_status"),
        ck("secret_policy", SECRET_POLICY_VALUES, "ck_channel_provider_configs_secret_policy"),
        sa.CheckConstraint("stores_plaintext_token = false", name="ck_channel_provider_configs_no_plaintext_token"),
    )
    op.create_index("idx_channel_provider_configs_provider_status", "channel_provider_configs", ["provider_id", "config_status"])
    op.create_index("idx_channel_provider_configs_user_status", "channel_provider_configs", ["user_id", "config_status"])

    op.create_table(
        "channel_bot_registries",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider_id", postgresql.UUID, nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=True),
        sa.Column("bot_key", sa.Text(), nullable=False),
        sa.Column("bot_display_name", sa.Text(), nullable=False),
        sa.Column("bot_status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("token_status", sa.Text(), nullable=False, server_default=sa.text("'missing'")),
        sa.Column("token_secret_ref", sa.Text(), nullable=True),
        sa.Column("stores_plaintext_token", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("external_application_id_hash", sa.Text(), nullable=True),
        sa.Column("external_bot_user_id_hash", sa.Text(), nullable=True),
        sa.Column("safe_metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["provider_id"], ["channel_providers.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.UniqueConstraint("provider_id", "bot_key", name="uq_channel_bot_registries_provider_bot_key"),
        ck("bot_status", BOT_STATUS_VALUES, "ck_channel_bot_registries_status"),
        ck("token_status", TOKEN_STATUS_VALUES, "ck_channel_bot_registries_token_status"),
        sa.CheckConstraint("stores_plaintext_token = false", name="ck_channel_bot_registries_no_plaintext_token"),
        sa.CheckConstraint(
            "token_status <> 'configured' OR token_secret_ref IS NOT NULL",
            name="ck_channel_bot_registries_configured_requires_secret_ref",
        ),
    )
    op.create_index("idx_channel_bot_registries_provider_status", "channel_bot_registries", ["provider_id", "bot_status"])
    op.create_index("idx_channel_bot_registries_user_status", "channel_bot_registries", ["user_id", "bot_status"])

    op.create_table(
        "channel_bindings",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("provider_id", postgresql.UUID, nullable=False),
        sa.Column("provider_bot_id", postgresql.UUID, nullable=True),
        sa.Column("presence_channel_binding_id", postgresql.UUID, nullable=True),
        sa.Column("binding_status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("binding_scope", sa.Text(), nullable=False, server_default=sa.text("'dm'")),
        sa.Column("permission_scope", sa.Text(), nullable=False, server_default=sa.text("'reply_only'")),
        sa.Column("outbound_policy", sa.Text(), nullable=False, server_default=sa.text("'reply_only'")),
        sa.Column("memory_policy", sa.Text(), nullable=False, server_default=sa.text("'ephemeral_review_gated'")),
        sa.Column("requires_user_approval", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("can_receive_inbound", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_send_outbound", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("checkin_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("memory_write_requires_review", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("raw_message_storage_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("stores_plaintext_token", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("external_channel_ref_hash", sa.Text(), nullable=True),
        sa.Column("external_user_ref_hash", sa.Text(), nullable=True),
        sa.Column("external_guild_ref_hash", sa.Text(), nullable=True),
        sa.Column("external_thread_ref_hash", sa.Text(), nullable=True),
        sa.Column("permission_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("boundary_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["provider_id"], ["channel_providers.id"]),
        sa.ForeignKeyConstraint(["provider_bot_id"], ["channel_bot_registries.id"]),
        sa.ForeignKeyConstraint(["presence_channel_binding_id"], ["presence_channel_bindings.id"]),
        ck("binding_status", BINDING_STATUS_VALUES, "ck_channel_bindings_status"),
        ck("binding_scope", BINDING_SCOPE_VALUES, "ck_channel_bindings_scope"),
        ck("permission_scope", PERMISSION_SCOPE_VALUES, "ck_channel_bindings_permission_scope"),
        ck("outbound_policy", OUTBOUND_POLICY_VALUES, "ck_channel_bindings_outbound_policy"),
        ck("memory_policy", MEMORY_POLICY_VALUES, "ck_channel_bindings_memory_policy"),
        sa.CheckConstraint("requires_user_approval = true", name="ck_channel_bindings_user_approval_required"),
        sa.CheckConstraint("stores_plaintext_token = false", name="ck_channel_bindings_no_plaintext_token"),
        sa.CheckConstraint("memory_write_requires_review = true", name="ck_channel_bindings_memory_review_required"),
        sa.CheckConstraint("raw_message_storage_allowed = false", name="ck_channel_bindings_no_raw_storage"),
        sa.CheckConstraint(
            "can_send_outbound = false OR outbound_policy <> 'disabled'",
            name="ck_channel_bindings_outbound_requires_policy",
        ),
        sa.CheckConstraint(
            "checkin_enabled = false OR permission_scope = 'low_frequency_checkin'",
            name="ck_channel_bindings_checkin_requires_scope",
        ),
        sa.CheckConstraint(
            "binding_status <> 'revoked' OR revoked_at IS NOT NULL",
            name="ck_channel_bindings_revoked_has_time",
        ),
    )
    op.create_index("idx_channel_bindings_user_status", "channel_bindings", ["user_id", "binding_status"])
    op.create_index("idx_channel_bindings_companion_status", "channel_bindings", ["companion_id", "binding_status"])
    op.create_index("idx_channel_bindings_provider_status", "channel_bindings", ["provider_id", "binding_status"])
    op.create_index("idx_channel_bindings_bot_status", "channel_bindings", ["provider_bot_id", "binding_status"])
    op.create_index("idx_channel_bindings_presence_bridge", "channel_bindings", ["presence_channel_binding_id"])


def downgrade() -> None:
    op.drop_index("idx_channel_bindings_presence_bridge", table_name="channel_bindings")
    op.drop_index("idx_channel_bindings_bot_status", table_name="channel_bindings")
    op.drop_index("idx_channel_bindings_provider_status", table_name="channel_bindings")
    op.drop_index("idx_channel_bindings_companion_status", table_name="channel_bindings")
    op.drop_index("idx_channel_bindings_user_status", table_name="channel_bindings")
    op.drop_table("channel_bindings")

    op.drop_index("idx_channel_bot_registries_user_status", table_name="channel_bot_registries")
    op.drop_index("idx_channel_bot_registries_provider_status", table_name="channel_bot_registries")
    op.drop_table("channel_bot_registries")

    op.drop_index("idx_channel_provider_configs_user_status", table_name="channel_provider_configs")
    op.drop_index("idx_channel_provider_configs_provider_status", table_name="channel_provider_configs")
    op.drop_table("channel_provider_configs")

    op.drop_index("idx_channel_providers_kind_status", table_name="channel_providers")
    op.drop_table("channel_providers")
