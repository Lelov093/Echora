"""PresenceOpportunity model."""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, Double, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDMixin, TimestampMixin, MetadataMixin, Base


class PresenceOpportunity(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "presence_opportunities"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_memory_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    evidence_message_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    evidence_growth_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )

    priority: Mapped[float] = mapped_column(Double, default=0.0)
    urgency: Mapped[float] = mapped_column(Double, default=0.0)
    sensitivity: Mapped[float] = mapped_column(Double, default=0.0)
    interruption_risk: Mapped[float] = mapped_column(Double, default=0.0)
    recommended_surface: Mapped[str] = mapped_column(String(50), default="queue")

    status: Mapped[str] = mapped_column(String(50), default="queued")
    snoozed_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user_action: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reward: Mapped[float | None] = mapped_column(Double, nullable=True)
    score_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    # ── Continuity: feedback / timing / calibration ────────────────────
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    dismissed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    suppress_type_rule_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    feedback_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feedback_events.id"), nullable=True
    )
    feedback_label: Mapped[str | None] = mapped_column(String, nullable=True)
    timing_score: Mapped[float] = mapped_column(Double, default=0.5)
    type_affinity_snapshot: Mapped[float] = mapped_column(Double, default=0.5)
    opportunity_context_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    meaningful_silence_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    calibration_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
