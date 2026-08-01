"""Add content-free proof for permanent Conversation deletion.

Revision ID: conversation_deletion_proof_v1
Revises: data_rights_deletion_v1
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "conversation_deletion_proof_v1"
down_revision = "data_rights_deletion_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversation_deletion_proofs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_scope_hash", sa.String(length=64), nullable=False),
        sa.Column("companion_scope_hash", sa.String(length=64), nullable=False),
        sa.Column("conversation_scope_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "deleted_counts_json",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversation_deletion_proof_scope",
        "conversation_deletion_proofs",
        ["user_id", "conversation_scope_hash"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_conversation_deletion_proof_scope",
        table_name="conversation_deletion_proofs",
    )
    op.drop_table("conversation_deletion_proofs")
