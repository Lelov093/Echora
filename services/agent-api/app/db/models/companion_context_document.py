"""Versioned Companion context documents used by the memory loop."""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, Double, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class MemoryContentRevision(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    """Immutable content snapshot for one Saved Memory revision."""

    __tablename__ = "memory_content_revisions"
    __table_args__ = (
        UniqueConstraint("memory_id", "revision", name="uq_memory_content_revision"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"), nullable=False)
    source_candidate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memory_candidates.id"), nullable=True)
    restored_from_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memory_content_revisions.id"), nullable=True)

    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    embedding_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    embedding_model: Mapped[str | None] = mapped_column(String(200), nullable=True)


class CompanionContextDocument(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    """Append-only version of a generated or user-corrected context document."""

    __tablename__ = "companion_context_documents"
    __table_args__ = (
        UniqueConstraint("companion_id", "document_kind", "version", name="uq_companion_context_document_version"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)
    supersedes_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companion_context_documents.id"), nullable=True)
    restored_from_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companion_context_documents.id"), nullable=True)

    document_kind: Mapped[str] = mapped_column(String(40), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    structured_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    source_message_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}", nullable=False)
    source_memory_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}", nullable=False)
    source_max_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    generation_reason: Mapped[str] = mapped_column(Text, nullable=False)
    generated_by_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    generated_by_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    user_corrected: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
