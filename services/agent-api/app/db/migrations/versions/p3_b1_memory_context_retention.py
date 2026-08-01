"""P3-B1 versioned Memory, context documents, and Conversation retention.

Revision ID: p3_b1_memory_context_retention
Revises: r1_b1_companion_governance
Create Date: 2026-07-16 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql


revision: str = "p3_b1_memory_context_retention"
down_revision: Union[str, Sequence[str], None] = "r1_b1_companion_governance"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("memories", sa.Column("content_revision", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("memories", sa.Column("content_hash", sa.String(length=64), nullable=True))
    op.execute("UPDATE memories SET content_hash = encode(digest(content, 'sha256'), 'hex') WHERE content_hash IS NULL")
    op.alter_column("memories", "content_hash", nullable=False)

    op.create_table(
        "memory_content_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("memory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_candidate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("restored_from_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("operation", sa.String(length=32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=True),
        sa.Column("embedding_provider", sa.String(length=100), nullable=True),
        sa.Column("embedding_model", sa.String(length=200), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["memory_id"], ["memories.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_candidate_id"], ["memory_candidates.id"]),
        sa.ForeignKeyConstraint(["restored_from_revision_id"], ["memory_content_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("memory_id", "revision", name="uq_memory_content_revision"),
        sa.CheckConstraint("revision >= 1", name="ck_memory_content_revision_positive"),
        sa.CheckConstraint("operation IN ('created','corrected','merged','restored')", name="ck_memory_content_revision_operation"),
    )
    op.create_index("idx_memory_content_revisions_scope", "memory_content_revisions", ["companion_id", "memory_id", "revision"])
    op.execute("""
        INSERT INTO memory_content_revisions (
            user_id, companion_id, memory_id, revision, content, summary,
            content_hash, operation, reason, embedding, metadata
        )
        SELECT user_id, companion_id, id, 1, content, summary, content_hash,
               'created', 'p3_b1_backfill_current_content', embedding,
               jsonb_build_object('backfilled', true)
        FROM memories
    """)

    op.create_table(
        "companion_context_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("supersedes_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("restored_from_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("document_kind", sa.String(length=40), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="active"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("structured_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("source_message_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default=sa.text("'{}'::uuid[]"), nullable=False),
        sa.Column("source_memory_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default=sa.text("'{}'::uuid[]"), nullable=False),
        sa.Column("source_max_message_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confidence", sa.Double(), nullable=False, server_default="0"),
        sa.Column("generation_reason", sa.Text(), nullable=False),
        sa.Column("generated_by_provider", sa.String(length=100), nullable=True),
        sa.Column("generated_by_model", sa.String(length=200), nullable=True),
        sa.Column("user_corrected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidation_reason", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["supersedes_document_id"], ["companion_context_documents.id"]),
        sa.ForeignKeyConstraint(["restored_from_document_id"], ["companion_context_documents.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("companion_id", "document_kind", "version", name="uq_companion_context_document_version"),
        sa.CheckConstraint("version >= 1", name="ck_companion_context_document_version"),
        sa.CheckConstraint("document_kind IN ('recent_summary','long_term_profile')", name="ck_companion_context_document_kind"),
        sa.CheckConstraint("status IN ('active','superseded','invalidated')", name="ck_companion_context_document_status"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_companion_context_document_confidence"),
    )
    op.create_index("idx_context_documents_active", "companion_context_documents", ["companion_id", "document_kind", "status", "version"])

    op.add_column("conversations", sa.Column("retention_mode", sa.String(length=32), nullable=False, server_default="standard"))
    op.add_column("conversations", sa.Column("cross_session_memory_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("conversations", sa.Column("history_visible", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("conversations", sa.Column("retention_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_conversations_retention_mode", "conversations", "retention_mode IN ('standard','temporary')")
    op.create_check_constraint(
        "ck_conversations_temporary_policy",
        "conversations",
        "retention_mode <> 'temporary' OR (cross_session_memory_enabled = false AND history_visible = false AND retention_expires_at IS NOT NULL)",
    )
    op.create_index("idx_conversations_retention_expiry", "conversations", ["retention_mode", "retention_expires_at"])


def downgrade() -> None:
    op.drop_index("idx_conversations_retention_expiry", table_name="conversations")
    op.drop_constraint("ck_conversations_temporary_policy", "conversations", type_="check")
    op.drop_constraint("ck_conversations_retention_mode", "conversations", type_="check")
    op.drop_column("conversations", "retention_expires_at")
    op.drop_column("conversations", "history_visible")
    op.drop_column("conversations", "cross_session_memory_enabled")
    op.drop_column("conversations", "retention_mode")
    op.drop_index("idx_context_documents_active", table_name="companion_context_documents")
    op.drop_table("companion_context_documents")
    op.drop_index("idx_memory_content_revisions_scope", table_name="memory_content_revisions")
    op.drop_table("memory_content_revisions")
    op.drop_column("memories", "content_hash")
    op.drop_column("memories", "content_revision")
