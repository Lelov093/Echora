"""Agent execution evidence, consistency, and outdated-memory models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Double, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class EvidenceSufficiencyEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "evidence_sufficiency_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"))
    trace_step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_steps.id"))
    target_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    sufficiency_score: Mapped[float] = mapped_column(Double, default=0.0)
    status: Mapped[str] = mapped_column(Text, default="needs_more_evidence")
    missing_evidence_json: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    evidence_refs: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    explanation: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class GrowthConsistencyCheck(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "growth_consistency_checks"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    growth_candidate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("growth_candidates.id"))
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"))
    consistency_score: Mapped[float] = mapped_column(Double, default=0.5)
    risk_level: Mapped[str] = mapped_column(Text, default="medium")
    status: Mapped[str] = mapped_column(Text, default="needs_review")
    conflict_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    duplication_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    profile_patch_preview_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    recommendation: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutdatedMemoryFlag(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "outdated_memory_flags"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id"), nullable=False)
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"))
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    confidence: Mapped[float] = mapped_column(Double, default=0.5)
    status: Mapped[str] = mapped_column(Text, default="open")
    evidence_refs: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    suggested_action: Mapped[str] = mapped_column(Text, default="review")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class OutdatedMemoryReview(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "outdated_memory_reviews"

    outdated_memory_flag_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("outdated_memory_flags.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id"), nullable=False)
    decision: Mapped[str] = mapped_column(Text, nullable=False)
    edited_content: Mapped[str | None] = mapped_column(Text)
    feedback_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("feedback_events.id"))
    lifecycle_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memory_lifecycle_events.id"))
    reason: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
