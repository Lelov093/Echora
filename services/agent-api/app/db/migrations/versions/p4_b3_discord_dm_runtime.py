"""Add durable Discord DM conversation bindings and delivery outbox.

Revision ID: p4_b3_discord_dm_runtime
Revises: p4_b2_tool_runtime
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p4_b3_discord_dm_runtime"
down_revision = "p4_b2_tool_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discord_dm_conversation_bindings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companions.id"), nullable=False),
        sa.Column("provider_bot_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("channel_bot_registries.id"), nullable=False),
        sa.Column("companion_channel_identity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companion_channel_identities.id"), nullable=False),
        sa.Column("channel_binding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("channel_bindings.id"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("external_user_ref_hash", sa.String(64), nullable=False),
        sa.Column("external_channel_ref_hash", sa.String(64), nullable=False),
        sa.Column("provider_channel_ref", sa.Text(), nullable=False),
        sa.Column("binding_status", sa.Text(), nullable=False, server_default="active"),
        sa.Column("binding_source", sa.Text(), nullable=False, server_default="first_dm"),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_inbound_at", sa.DateTime(timezone=True)),
        sa.Column("last_outbound_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("binding_status IN ('active','paused','revoked')", name="ck_discord_dm_bindings_status"),
        sa.CheckConstraint("binding_source IN ('first_dm','web','slash_command')", name="ck_discord_dm_bindings_source"),
        sa.CheckConstraint("revision >= 1", name="ck_discord_dm_bindings_revision"),
    )
    op.create_index(
        "uq_discord_dm_binding_identity",
        "discord_dm_conversation_bindings",
        ["provider_bot_id", "external_user_ref_hash"],
        unique=True,
    )
    op.create_index("idx_discord_dm_bindings_scope", "discord_dm_conversation_bindings", ["user_id", "companion_id", "binding_status"])

    op.create_table(
        "discord_dm_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companions.id"), nullable=False),
        sa.Column("dm_binding_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("discord_dm_conversation_bindings.id"), nullable=False),
        sa.Column("channel_delivery_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("channel_delivery_events.id")),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("assistant_message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id"), nullable=False),
        sa.Column("trace_run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("trace_runs.id")),
        sa.Column("inbound_message_ref_hash", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("delivery_status", sa.Text(), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True)),
        sa.Column("lease_owner", sa.Text()),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("provider_message_ref_hash", sa.String(64)),
        sa.Column("last_error_code", sa.Text()),
        sa.Column("last_error_summary", sa.Text()),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("cancelled_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.CheckConstraint("delivery_status IN ('queued','leased','retry_scheduled','delivered','failed','cancelled','suppressed')", name="ck_discord_dm_deliveries_status"),
        sa.CheckConstraint("attempt_count >= 0 AND max_attempts BETWEEN 1 AND 10", name="ck_discord_dm_deliveries_attempts"),
        sa.UniqueConstraint("idempotency_key", name="uq_discord_dm_deliveries_idempotency"),
    )
    op.create_index("idx_discord_dm_deliveries_due", "discord_dm_deliveries", ["delivery_status", "next_attempt_at", "lease_expires_at"])
    op.create_index("idx_discord_dm_deliveries_scope", "discord_dm_deliveries", ["user_id", "companion_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_discord_dm_deliveries_scope", table_name="discord_dm_deliveries")
    op.drop_index("idx_discord_dm_deliveries_due", table_name="discord_dm_deliveries")
    op.drop_table("discord_dm_deliveries")
    op.drop_index("idx_discord_dm_bindings_scope", table_name="discord_dm_conversation_bindings")
    op.drop_index("uq_discord_dm_binding_identity", table_name="discord_dm_conversation_bindings")
    op.drop_table("discord_dm_conversation_bindings")
