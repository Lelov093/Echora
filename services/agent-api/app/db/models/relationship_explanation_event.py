"""RelationshipExplanationEvent — relationship dimension change explanations (Continuity)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Double, ForeignKey, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDMixin, TimestampMixin, MetadataMixin, SoftDeleteMixin


class RelationshipExplanationEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin, SoftDeleteMixin):
    __tablename__ = "relationship_explanation_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True)
    relationship_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("relationship_events.id"), nullable=True)
    feedback_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("feedback_events.id"), nullable=True)

    dimension: Mapped[str] = mapped_column(String, nullable=False)
    previous_value: Mapped[float | None] = mapped_column(Double, nullable=True)
    new_value: Mapped[float | None] = mapped_column(Double, nullable=True)
    delta: Mapped[float | None] = mapped_column(Double, nullable=True)

    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_memory_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default="{}")
    evidence_message_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default="{}")
    evidence_growth_record_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default="{}")

    confidence: Mapped[float] = mapped_column(Double, nullable=False, default=0.5)
    user_visible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    score_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    impact_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
