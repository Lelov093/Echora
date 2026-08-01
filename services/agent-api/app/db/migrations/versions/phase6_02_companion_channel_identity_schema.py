"""phase6_02_companion_channel_identity_schema

Revision ID: p6_02_channel_identity
Revises: p6_01_channel_gateway
Create Date: 2026-06-03 00:00:00.000000

Upgrade Phase 5 readiness companion channel identity records into Phase 6
Companion Channel Identity / Persona Projection schema. This preserves the
existing companions main entity and adds channel-specific projection fields
without creating a global single-bot identity.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p6_02_channel_identity"
down_revision: Union[str, Sequence[str], None] = "p6_01_channel_gateway"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CHANNEL_STATUS_VALUES = ("draft", "active", "disabled", "revoked")
CHANNEL_PRESENCE_STYLE_VALUES = ("inherit_companion", "quiet", "balanced", "expressive")
PERSONA_PROJECTION_MODE_VALUES = ("disabled", "summary_only", "explicit_user_authorization")
IDENTITY_SCOPE_VALUES = ("mock_projection", "discord_bot_identity")


def ck(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=name)


def upgrade() -> None:
    op.add_column("companion_channel_identities", sa.Column("channel_binding_id", postgresql.UUID, nullable=True))
    op.add_column("companion_channel_identities", sa.Column("provider_bot_id", postgresql.UUID, nullable=True))
    op.add_column(
        "companion_channel_identities",
        sa.Column("identity_scope", sa.Text(), nullable=False, server_default=sa.text("'mock_projection'")),
    )
    op.add_column(
        "companion_channel_identities",
        sa.Column("channel_status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
    )
    op.add_column("companion_channel_identities", sa.Column("channel_display_name", sa.Text(), nullable=True))
    op.add_column("companion_channel_identities", sa.Column("channel_avatar_placeholder", sa.Text(), nullable=True))
    op.add_column(
        "companion_channel_identities",
        sa.Column("channel_persona_projection", sa.Text(), nullable=False, server_default=sa.text("''")),
    )
    op.add_column(
        "companion_channel_identities",
        sa.Column(
            "channel_persona_projection_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "companion_channel_identities",
        sa.Column("channel_presence_style", sa.Text(), nullable=False, server_default=sa.text("'inherit_companion'")),
    )
    op.add_column(
        "companion_channel_identities",
        sa.Column(
            "channel_boundary_profile",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "companion_channel_identities",
        sa.Column("persona_projection_mode", sa.Text(), nullable=False, server_default=sa.text("'summary_only'")),
    )
    op.add_column(
        "companion_channel_identities",
        sa.Column("private_memory_visible_by_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "companion_channel_identities",
        sa.Column("uses_single_global_bot_gateway", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "companion_channel_identities",
        sa.Column("is_global_bot_identity", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_foreign_key(
        "fk_cci_channel_binding_id",
        "companion_channel_identities",
        "channel_bindings",
        ["channel_binding_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_cci_provider_bot_id",
        "companion_channel_identities",
        "channel_bot_registries",
        ["provider_bot_id"],
        ["id"],
    )

    op.create_check_constraint(
        "ck_cci_phase6_channel_status",
        "companion_channel_identities",
        "channel_status IN ('draft', 'active', 'disabled', 'revoked')",
    )
    op.create_check_constraint(
        "ck_cci_phase6_presence_style",
        "companion_channel_identities",
        "channel_presence_style IN ('inherit_companion', 'quiet', 'balanced', 'expressive')",
    )
    op.create_check_constraint(
        "ck_cci_phase6_projection_mode",
        "companion_channel_identities",
        "persona_projection_mode IN ('disabled', 'summary_only', 'explicit_user_authorization')",
    )
    op.create_check_constraint(
        "ck_cci_phase6_identity_scope",
        "companion_channel_identities",
        "identity_scope IN ('mock_projection', 'discord_bot_identity')",
    )
    op.create_check_constraint(
        "ck_cci_phase6_no_private_memory_default",
        "companion_channel_identities",
        "private_memory_visible_by_default = false",
    )
    op.create_check_constraint(
        "ck_cci_phase6_no_single_global_bot_gateway",
        "companion_channel_identities",
        "uses_single_global_bot_gateway = false",
    )
    op.create_check_constraint(
        "ck_cci_phase6_not_global_bot_identity",
        "companion_channel_identities",
        "is_global_bot_identity = false",
    )
    op.create_check_constraint(
        "ck_cci_phase6_discord_requires_bot",
        "companion_channel_identities",
        "identity_scope <> 'discord_bot_identity' OR provider_bot_id IS NOT NULL",
    )

    op.create_index("idx_cci_phase6_channel_binding", "companion_channel_identities", ["channel_binding_id"])
    op.create_index("idx_cci_phase6_provider_bot", "companion_channel_identities", ["provider_bot_id"])
    op.create_index(
        "idx_cci_phase6_companion_channel_status",
        "companion_channel_identities",
        ["companion_id", "channel_status"],
    )


def downgrade() -> None:
    op.drop_index("idx_cci_phase6_companion_channel_status", table_name="companion_channel_identities")
    op.drop_index("idx_cci_phase6_provider_bot", table_name="companion_channel_identities")
    op.drop_index("idx_cci_phase6_channel_binding", table_name="companion_channel_identities")

    op.drop_constraint("ck_cci_phase6_discord_requires_bot", "companion_channel_identities", type_="check")
    op.drop_constraint("ck_cci_phase6_not_global_bot_identity", "companion_channel_identities", type_="check")
    op.drop_constraint("ck_cci_phase6_no_single_global_bot_gateway", "companion_channel_identities", type_="check")
    op.drop_constraint("ck_cci_phase6_no_private_memory_default", "companion_channel_identities", type_="check")
    op.drop_constraint("ck_cci_phase6_identity_scope", "companion_channel_identities", type_="check")
    op.drop_constraint("ck_cci_phase6_projection_mode", "companion_channel_identities", type_="check")
    op.drop_constraint("ck_cci_phase6_presence_style", "companion_channel_identities", type_="check")
    op.drop_constraint("ck_cci_phase6_channel_status", "companion_channel_identities", type_="check")

    op.drop_constraint("fk_cci_provider_bot_id", "companion_channel_identities", type_="foreignkey")
    op.drop_constraint("fk_cci_channel_binding_id", "companion_channel_identities", type_="foreignkey")

    op.drop_column("companion_channel_identities", "is_global_bot_identity")
    op.drop_column("companion_channel_identities", "uses_single_global_bot_gateway")
    op.drop_column("companion_channel_identities", "private_memory_visible_by_default")
    op.drop_column("companion_channel_identities", "persona_projection_mode")
    op.drop_column("companion_channel_identities", "channel_boundary_profile")
    op.drop_column("companion_channel_identities", "channel_presence_style")
    op.drop_column("companion_channel_identities", "channel_persona_projection_json")
    op.drop_column("companion_channel_identities", "channel_persona_projection")
    op.drop_column("companion_channel_identities", "channel_avatar_placeholder")
    op.drop_column("companion_channel_identities", "channel_display_name")
    op.drop_column("companion_channel_identities", "channel_status")
    op.drop_column("companion_channel_identities", "identity_scope")
    op.drop_column("companion_channel_identities", "provider_bot_id")
    op.drop_column("companion_channel_identities", "channel_binding_id")
