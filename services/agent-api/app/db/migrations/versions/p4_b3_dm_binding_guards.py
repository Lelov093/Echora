"""Enforce one live Discord DM identity per bot while preserving revoked history.

Revision ID: p4_b3_dm_binding_guards
Revises: p4_b3_discord_dm_runtime
"""

from alembic import op
import sqlalchemy as sa


revision = "p4_b3_dm_binding_guards"
down_revision = "p4_b3_discord_dm_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("uq_discord_dm_binding_identity", table_name="discord_dm_conversation_bindings")
    op.create_index(
        "uq_discord_dm_binding_live_identity",
        "discord_dm_conversation_bindings",
        ["provider_bot_id", "external_user_ref_hash"],
        unique=True,
        postgresql_where=sa.text("binding_status IN ('active','paused')"),
    )
    op.create_index(
        "uq_discord_dm_binding_live_bot",
        "discord_dm_conversation_bindings",
        ["provider_bot_id"],
        unique=True,
        postgresql_where=sa.text("binding_status IN ('active','paused')"),
    )


def downgrade() -> None:
    op.drop_index("uq_discord_dm_binding_live_bot", table_name="discord_dm_conversation_bindings")
    op.drop_index("uq_discord_dm_binding_live_identity", table_name="discord_dm_conversation_bindings")
    op.create_index(
        "uq_discord_dm_binding_identity",
        "discord_dm_conversation_bindings",
        ["provider_bot_id", "external_user_ref_hash"],
        unique=True,
    )
