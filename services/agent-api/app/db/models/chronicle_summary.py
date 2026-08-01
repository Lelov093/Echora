"""Versioned derived summaries for one Companion's confirmed Chronicle."""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class CompanionChronicleSummary(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_chronicle_summaries"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    highlights_json: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    source_event_refs: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, server_default="{}", nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    generated_by_provider: Mapped[str] = mapped_column(String(100), nullable=False)
    generated_by_model: Mapped[str | None] = mapped_column(String(200), nullable=True)
    supersedes_summary_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companion_chronicle_summaries.id"), nullable=True)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    invalidation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (UniqueConstraint("companion_id", "version", name="uq_companion_chronicle_summary_version"),)
