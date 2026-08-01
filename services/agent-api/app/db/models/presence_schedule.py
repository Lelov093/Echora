"""Durable Presence scheduling and delivery records."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class PresenceSchedule(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "presence_schedules"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="paused", nullable=False)
    pause_reason: Mapped[str | None] = mapped_column(Text)

    destination_mode: Mapped[str] = mapped_column(String(40), default="bound_conversation", nullable=False)
    bound_conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    latest_created_conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )

    timezone: Mapped[str] = mapped_column(String(100), default="UTC", nullable=False)
    weekdays: Mapped[list[int]] = mapped_column(
        ARRAY(Integer),
        default=lambda: list(range(7)),
        server_default=text("'{0,1,2,3,4,5,6}'::integer[]"),
        nullable=False,
    )
    timing_mode: Mapped[str] = mapped_column(String(20), default="fixed", nullable=False)
    fixed_minute_of_day: Mapped[int] = mapped_column(Integer, default=1200, nullable=False)
    window_start_minute: Mapped[int] = mapped_column(Integer, default=1140, nullable=False)
    window_end_minute: Mapped[int] = mapped_column(Integer, default=1320, nullable=False)
    cadence_mode: Mapped[str] = mapped_column(String(20), default="fixed", nullable=False)
    fixed_interval_minutes: Mapped[int] = mapped_column(Integer, default=1440, nullable=False)
    random_interval_min_minutes: Mapped[int] = mapped_column(Integer, default=1440, nullable=False)
    random_interval_max_minutes: Mapped[int] = mapped_column(Integer, default=4320, nullable=False)

    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    occurrence_sequence: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_occurrence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (UniqueConstraint("user_id", "companion_id", name="uq_presence_schedule_scope"),)


class PresenceScheduleOccurrence(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "presence_schedule_occurrences"

    schedule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presence_schedules.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    schedule_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(24), default="scheduled", nullable=False)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    presence_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presence_opportunities.id")
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id"))
    suppression_reason: Mapped[str | None] = mapped_column(String(100))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_summary: Mapped[str | None] = mapped_column(Text)
    random_draw_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False)
    delivery_evidence_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"), nullable=False)

    __table_args__ = (
        UniqueConstraint("schedule_id", "sequence_no", name="uq_presence_occurrence_sequence"),
    )
