"""MemoryAbstractionCandidate — high-level understanding abstractions (Continuity)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Double, ForeignKey, Integer, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDMixin, TimestampMixin, MetadataMixin, SoftDeleteMixin


class MemoryAbstractionCandidate(Base, UUIDMixin, TimestampMixin, MetadataMixin, SoftDeleteMixin):
    __tablename__ = "memory_abstraction_candidates"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True)

    source_memory_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default="{}")
    source_message_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default="{}")
    source_feedback_event_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default="{}")

    abstraction_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_memory_type: Mapped[str | None] = mapped_column(String, nullable=True)
    suggested_growth_type: Mapped[str | None] = mapped_column(String, nullable=True)

    evidence_score: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Double, nullable=False, default=0.5)
    recurrence: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    consistency_score: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    risk_score: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    impact_preview: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    evidence_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    cluster_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")

    status: Mapped[str] = mapped_column(String, nullable=False, default="candidate")
    accepted_memory_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id"), nullable=True)
    accepted_growth_record_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("growth_records.id"), nullable=True)
    edited_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
