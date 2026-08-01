"""Companion shared scene ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class SharedScene(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "shared_scenes"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    owner_companion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True
    )
    scene_title: Mapped[str] = mapped_column(Text, default="")
    scene_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    scene_type: Mapped[str] = mapped_column(Text, default="conversation")
    scene_status: Mapped[str] = mapped_column(Text, default="active")
    source_type: Mapped[str] = mapped_column(Text, default="co_presence_session")
    focal_topic: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility_scope: Mapped[str] = mapped_column(Text, default="role_summary")
    context_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    visibility_policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SharedSceneEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "shared_scene_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    shared_scene_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shared_scenes.id"), nullable=False)
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_participants.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(Text, default="scene_note")
    event_source: Mapped[str] = mapped_column(Text, default="system")
    title: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str | None] = mapped_column(Text, nullable=True)
    visibility_scope: Mapped[str] = mapped_column(Text, default="role_summary")
    triggers_shared_experience_candidate: Mapped[bool] = mapped_column(Boolean, default=False)
    event_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SharedExperienceRecord(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "shared_experience_records"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    shared_scene_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_scenes.id"), nullable=True
    )
    source_scene_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_scene_events.id"), nullable=True
    )
    source_conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    source_trace_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(Text, default="session")
    experience_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience_summary: Mapped[str] = mapped_column(Text, default="")
    experience_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    experience_status: Mapped[str] = mapped_column(Text, default="captured")
    recommended_memory_action: Mapped[str] = mapped_column(Text, default="shared_candidate")
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_participants.id"), nullable=True
    )
    approved_shared_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_episodic_memories.id"), nullable=True
    )
    policy_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


__all__ = [
    "SharedScene",
    "SharedSceneEvent",
    "SharedExperienceRecord",
]
