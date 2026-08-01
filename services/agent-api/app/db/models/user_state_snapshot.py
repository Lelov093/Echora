"""UserStateSnapshot — EWMA-smoothed low-risk user state (Continuity)."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Double, ForeignKey, Integer, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDMixin, TimestampMixin, MetadataMixin


class UserStateSnapshot(Base, UUIDMixin, MetadataMixin):
    __tablename__ = "user_state_snapshots"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True)

    signal_type: Mapped[str] = mapped_column(String, nullable=False)
    mode_key: Mapped[str | None] = mapped_column(String, nullable=True)

    observed_value: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    previous_smoothed_value: Mapped[float | None] = mapped_column(Double, nullable=True)
    smoothed_value: Mapped[float] = mapped_column(Double, nullable=False, default=0.0)
    smoothing_factor: Mapped[float] = mapped_column(Double, nullable=False, default=0.8)

    confidence: Mapped[float] = mapped_column(Double, nullable=False, default=0.5)
    source_event_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    observation_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observation_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_feedback_event_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default="{}")
    source_trace_run_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default="{}")

    state_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), server_default=func.now(), nullable=False
    )
