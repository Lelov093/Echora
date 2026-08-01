"""ContinuitySnapshot — structured continuity snapshots (Continuity)."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Double, ForeignKey, String, Text, DateTime, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UUIDMixin, TimestampMixin, MetadataMixin, SoftDeleteMixin


class ContinuitySnapshot(Base, UUIDMixin, TimestampMixin, MetadataMixin, SoftDeleteMixin):
    __tablename__ = "continuity_snapshots"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True)
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    shared_scene_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_scenes.id"), nullable=True
    )

    snapshot_type: Mapped[str] = mapped_column(String, nullable=False, default="agent_run")
    mode_key: Mapped[str] = mapped_column(String, nullable=False, default="project")

    current_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_phase: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_user_intent: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_assistant_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    open_threads: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    unresolved_decisions: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    pending_reviews: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    suggested_next_steps: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list, server_default="[]")
    relevant_memory_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default="{}")
    relevant_growth_record_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default="{}")
    relevant_presence_opportunity_ids: Mapped[list] = mapped_column(ARRAY(UUID(as_uuid=True)), nullable=False, default=list, server_default="{}")

    continuity_score: Mapped[float] = mapped_column(Double, nullable=False, default=0.5)
    freshness_score: Mapped[float] = mapped_column(Double, nullable=False, default=0.5)
    user_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    feedback_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("feedback_events.id"), nullable=True)

    snapshot_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict, server_default="{}")
    participant_awareness_json: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
