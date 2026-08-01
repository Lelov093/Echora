"""Conversation model."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Double, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import UUIDMixin, TimestampMixin, SoftDeleteMixin, MetadataMixin, Base


class Conversation(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, MetadataMixin):
    __tablename__ = "conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    shared_scene_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_scenes.id"), nullable=True
    )

    title: Mapped[str] = mapped_column(String(500), default="New Conversation")
    mode_key: Mapped[str] = mapped_column(String(50), default="project")
    status: Mapped[str] = mapped_column(String(50), default="active")
    retention_mode: Mapped[str] = mapped_column(String(32), default="standard", nullable=False)
    cross_session_memory_enabled: Mapped[bool] = mapped_column(default=True, nullable=False)
    history_visible: Mapped[bool] = mapped_column(default=True, nullable=False)
    retention_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    current_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    working_memory_snapshot: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    continuity_state: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    # ── Continuity: continuity ─────────────────────────────────────────
    continuity_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    latest_continuity_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("continuity_snapshots.id"), nullable=True
    )
    open_thread_count: Mapped[int] = mapped_column(Integer, default=0)
    pending_review_count: Mapped[int] = mapped_column(Integer, default=0)
    unresolved_decision_count: Mapped[int] = mapped_column(Integer, default=0)
    next_step_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    continuity_score: Mapped[float] = mapped_column(Double, default=0.5)

    messages = relationship("Message", back_populates="conversation", lazy="selectin")
