"""Add durable Discord Channel ingress and correct-Bot Room outbox.

Revision ID: p5_b3_discord_room_runtime
Revises: p5_b2_room_turn_step_lease
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p5_b3_discord_room_runtime"
down_revision = "p5_b2_room_turn_step_lease"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "discord_channel_ingresses",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discord_channel_room_binding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discord_text_channel_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("room_turn_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("user_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("provider_guild_ref_hash", sa.String(length=64), nullable=False),
        sa.Column("provider_channel_ref_hash", sa.String(length=64), nullable=False),
        sa.Column("provider_message_ref_hash", sa.String(length=64), nullable=False),
        sa.Column("external_author_ref_hash", sa.String(length=64), nullable=False),
        sa.Column("author_display_name", sa.String(length=200), nullable=False, server_default="Discord user"),
        sa.Column("observed_bot_key", sa.String(length=120), nullable=False),
        sa.Column("ingress_status", sa.String(length=32), nullable=False, server_default="received"),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("mentioned_bot_keys_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("selected_companion_ids_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("evidence_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["discord_channel_room_binding_id"], ["discord_channel_room_bindings.id"]),
        sa.ForeignKeyConstraint(["discord_text_channel_id"], ["discord_text_channels.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["room_turn_id"], ["companion_room_turns.id"]),
        sa.ForeignKeyConstraint(["user_message_id"], ["messages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("provider_guild_ref_hash", "provider_channel_ref_hash", "provider_message_ref_hash", name="uq_discord_channel_ingress_provider_message"),
        sa.CheckConstraint("ingress_status IN ('received','processing','completed','partial_failed','suppressed','failed','ignored')", name="ck_discord_channel_ingress_status"),
    )
    op.create_index("ix_discord_channel_ingress_binding_created", "discord_channel_ingresses", ["discord_channel_room_binding_id", "created_at"])
    op.create_table(
        "discord_channel_deliveries",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discord_channel_ingress_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("discord_channel_room_binding_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("room_turn_step_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider_bot_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assistant_message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("trace_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("delivery_status", sa.String(length=32), nullable=False, server_default="queued"),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_owner", sa.String(length=160), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_message_ref_hash", sa.String(length=64), nullable=True),
        sa.Column("last_error_code", sa.String(length=120), nullable=True),
        sa.Column("last_error_summary", sa.String(length=500), nullable=True),
        sa.Column("error_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["discord_channel_ingress_id"], ["discord_channel_ingresses.id"]),
        sa.ForeignKeyConstraint(["discord_channel_room_binding_id"], ["discord_channel_room_bindings.id"]),
        sa.ForeignKeyConstraint(["room_turn_step_id"], ["companion_room_turn_steps.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["provider_bot_id"], ["channel_bot_registries.id"]),
        sa.ForeignKeyConstraint(["assistant_message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["trace_run_id"], ["trace_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("discord_channel_ingress_id", "room_turn_step_id", name="uq_discord_channel_delivery_step"),
        sa.UniqueConstraint("idempotency_key", name="uq_discord_channel_delivery_idempotency"),
        sa.CheckConstraint("delivery_status IN ('queued','leased','retry_scheduled','delivered','failed','cancelled','suppressed')", name="ck_discord_channel_delivery_status"),
    )
    op.create_index("ix_discord_channel_delivery_due", "discord_channel_deliveries", ["delivery_status", "next_attempt_at", "lease_expires_at"])


def downgrade() -> None:
    op.drop_index("ix_discord_channel_delivery_due", table_name="discord_channel_deliveries")
    op.drop_table("discord_channel_deliveries")
    op.drop_index("ix_discord_channel_ingress_binding_created", table_name="discord_channel_ingresses")
    op.drop_table("discord_channel_ingresses")
