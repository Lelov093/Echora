"""MemoryLifecycleEvent — memory lifecycle timeline events (Continuity)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Double, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDMixin, MetadataMixin


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryLifecycleEvent(Base, UUIDMixin, MetadataMixin):
    __tablename__ = "memory_lifecycle_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)
    message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True)

    memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id"), nullable=False)
    source_candidate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memory_candidates.id"), nullable=True)
    feedback_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("feedback_events.id"), nullable=True)

    event_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    previous_state: Mapped[str | None] = mapped_column(String, nullable=True)
    new_state: Mapped[str | None] = mapped_column(String, nullable=True)

    previous_strength: Mapped[float | None] = mapped_column(Double, nullable=True)
    new_strength: Mapped[float | None] = mapped_column(Double, nullable=True)
    strength_delta: Mapped[float | None] = mapped_column(Double, nullable=True)

    previous_confidence: Mapped[float | None] = mapped_column(Double, nullable=True)
    new_confidence: Mapped[float | None] = mapped_column(Double, nullable=True)
    confidence_delta: Mapped[float | None] = mapped_column(Double, nullable=True)

    previous_half_life_days: Mapped[float | None] = mapped_column(Double, nullable=True)
    new_half_life_days: Mapped[float | None] = mapped_column(Double, nullable=True)

    score_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    before_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    after_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, server_default=func.now(), nullable=False
    )
