"""Agent execution file context models."""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, DateTime, Double, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class FileSource(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "file_sources"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    uri: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="active")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FileDocument(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "file_documents"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    file_source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("file_sources.id"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    document_type: Mapped[str] = mapped_column(Text, default="unknown")
    status: Mapped[str] = mapped_column(Text, default="created")
    mime_type: Mapped[str | None] = mapped_column(Text)
    uri: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    processing_error: Mapped[str | None] = mapped_column(Text)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FileChunk(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "file_chunks"

    file_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("file_documents.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="ready")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text)
    token_count: Mapped[int | None] = mapped_column(Integer)
    embedding = mapped_column(Vector(1024), nullable=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class FileContextUsage(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "file_context_usages"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id"))
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"))
    trace_step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_steps.id"))
    file_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("file_documents.id"))
    file_chunk_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}")
    usage_purpose: Mapped[str] = mapped_column(Text, default="response_generation")
    selected_for_context: Mapped[bool] = mapped_column(default=False)
    used_in_response: Mapped[bool] = mapped_column(default=False)
    evidence_score: Mapped[float] = mapped_column(Double, default=0.0)
    citation_json: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
