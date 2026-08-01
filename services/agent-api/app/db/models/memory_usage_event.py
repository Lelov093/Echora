"""MemoryUsageEvent — how/when/why memories were used (Continuity)."""

import uuid
from sqlalchemy import Boolean, Double, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDMixin, TimestampMixin, MetadataMixin


class MemoryUsageEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "memory_usage_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)
    message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True)
    trace_step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_steps.id"), nullable=True)

    memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)

    semantic_similarity: Mapped[float | None] = mapped_column(Double, nullable=True)
    retrieval_score: Mapped[float | None] = mapped_column(Double, nullable=True)
    memory_strength_snapshot: Mapped[float | None] = mapped_column(Double, nullable=True)
    confidence_snapshot: Mapped[float | None] = mapped_column(Double, nullable=True)
    goal_relevance_snapshot: Mapped[float | None] = mapped_column(Double, nullable=True)
    relationship_impact_snapshot: Mapped[float | None] = mapped_column(Double, nullable=True)

    rank_before_rerank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rank_after_rerank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    selected_for_context: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    used_in_response: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    used_in_growth: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    used_in_presence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    used_in_relationship: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    why_selected: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_excluded: Mapped[str | None] = mapped_column(Text, nullable=True)

    feedback_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("feedback_events.id"), nullable=True)
    feedback_label: Mapped[str | None] = mapped_column(String, nullable=True)

    score_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    usage_context: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
