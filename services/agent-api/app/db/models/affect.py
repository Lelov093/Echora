"""Companion-scoped affect state and immutable appraisal events."""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, Double, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class CompanionAffectState(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_affect_states"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    valence: Mapped[float] = mapped_column(Double, default=0.08, nullable=False)
    arousal: Mapped[float] = mapped_column(Double, default=-0.08, nullable=False)
    home_valence: Mapped[float] = mapped_column(Double, default=0.08, nullable=False)
    home_arousal: Mapped[float] = mapped_column(Double, default=-0.08, nullable=False)
    half_life_hours: Mapped[float] = mapped_column(Double, default=18.0, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    last_transition_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expression_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expression_intensity: Mapped[str] = mapped_column(String(16), default="subtle", nullable=False)
    expression_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)

    __table_args__ = (UniqueConstraint("user_id", "companion_id", name="uq_companion_affect_scope"),)


class CompanionAffectEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_affect_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    source_message_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    operation: Mapped[str] = mapped_column(String(20), default="appraised", nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_quote: Mapped[str] = mapped_column(Text, nullable=False)
    appraisal_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    transition_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    extraction_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    validation_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    state_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    supersedes_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companion_affect_events.id"), nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    algorithm_version: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), unique=True, nullable=False)
    invalidated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
