"""Unified feedback and calibration sample model."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Double, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class FeedbackEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "feedback_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id"))
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"))

    target_type: Mapped[str] = mapped_column(String, nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    action: Mapped[str] = mapped_column(String, nullable=False)
    label: Mapped[str] = mapped_column(String, nullable=False, default="neutral")
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    feedback_source: Mapped[str] = mapped_column(String, nullable=False, default="explicit")
    reward: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    reason: Mapped[str | None] = mapped_column(Text)
    user_note: Mapped[str | None] = mapped_column(Text)

    score_delta: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    confidence_delta: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    strength_delta: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    priority_delta: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)

    applies_to_memory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    applies_to_growth: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    applies_to_presence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    applies_to_retrieval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    applies_to_relationship: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    applies_to_boundary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    calibration_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    context_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    sample_provenance: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    context_hash: Mapped[str | None] = mapped_column(Text)
    algorithm_key: Mapped[str | None] = mapped_column(Text)
    algorithm_version: Mapped[str] = mapped_column(Text, nullable=False, default="core-feedback-v1")
    risk_level: Mapped[str] = mapped_column(String, nullable=False, default="low")
    redaction_status: Mapped[str] = mapped_column(String, nullable=False, default="not_required")
    training_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    before_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    after_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
