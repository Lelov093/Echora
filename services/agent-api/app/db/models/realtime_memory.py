"""Realtime compatibility realtime memory buffer ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Double, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class RealtimeMemoryBuffer(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "realtime_memory_buffers"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=False
    )
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    shared_scene_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("shared_scenes.id"), nullable=True)
    owner_companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True)
    buffer_scope: Mapped[str] = mapped_column(Text, default="co_presence_session")
    buffer_status: Mapped[str] = mapped_column(Text, default="active")
    default_memory_action: Mapped[str] = mapped_column(Text, default="candidate_review")
    retention_policy: Mapped[str] = mapped_column(Text, default="ephemeral")
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_write_private_memory: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_write_shared_memory: Mapped[bool] = mapped_column(Boolean, default=False)
    buffer_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RealtimeMemoryBufferItem(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "realtime_memory_buffer_items"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    buffer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_memory_buffers.id"), nullable=False)
    realtime_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(Text, default="session_event")
    source_voice_turn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("voice_turns.id"), nullable=True)
    source_context_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("multimodal_context_events.id"), nullable=True)
    source_session_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_session_state_events.id"), nullable=True
    )
    source_channel_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_channel_state_events.id"), nullable=True
    )
    item_status: Mapped[str] = mapped_column(Text, default="active")
    retention_policy: Mapped[str] = mapped_column(Text, default="ephemeral")
    content_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_content_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    can_generate_salient_moment: Mapped[bool] = mapped_column(Boolean, default=True)
    can_write_long_term_memory: Mapped[bool] = mapped_column(Boolean, default=False)
    payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CompanionPrivateRealtimeBuffer(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_private_realtime_buffers"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    buffer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_memory_buffers.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    private_memory_sync_policy: Mapped[str] = mapped_column(Text, default="review_required")
    auto_write_private_memory: Mapped[bool] = mapped_column(Boolean, default=False)
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class CoPresenceSessionBuffer(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "copresence_session_buffers"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    buffer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_memory_buffers.id"), nullable=False)
    co_presence_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=False)
    shared_candidate_policy: Mapped[str] = mapped_column(Text, default="review_required")
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class SharedSceneBuffer(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "shared_scene_buffers"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    buffer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_memory_buffers.id"), nullable=False)
    shared_scene_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("shared_scenes.id"), nullable=False)
    shared_candidate_policy: Mapped[str] = mapped_column(Text, default="review_required")
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class SalientMoment(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "salient_moments"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=False
    )
    buffer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_memory_buffers.id"), nullable=True)
    buffer_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_memory_buffer_items.id"), nullable=True
    )
    moment_scope: Mapped[str] = mapped_column(Text, default="shared_episodic")
    moment_status: Mapped[str] = mapped_column(Text, default="candidate_pending_review")
    moment_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    moment_summary: Mapped[str] = mapped_column(Text, default="")
    salience_score: Mapped[float] = mapped_column(Double, default=0.5)
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_write_disabled: Mapped[bool] = mapped_column(Boolean, default=True)
    evidence_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    policy_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class CompanionPrivateSalientMoment(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_private_salient_moments"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    salient_moment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("salient_moments.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    private_memory_sync_policy: Mapped[str] = mapped_column(Text, default="review_required")
    approved_private_memory_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id"), nullable=True)
    auto_write_private_memory: Mapped[bool] = mapped_column(Boolean, default=False)
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)


class SharedSalientMoment(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "shared_salient_moments"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    salient_moment_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("salient_moments.id"), nullable=False)
    shared_scene_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("shared_scenes.id"), nullable=True)
    proposed_shared_memory_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_memory_candidates.id"), nullable=True
    )
    shared_memory_sync_policy: Mapped[str] = mapped_column(Text, default="review_required")
    auto_write_shared_memory: Mapped[bool] = mapped_column(Boolean, default=False)
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)


class RealtimeSharedMemoryCandidate(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "realtime_shared_memory_candidates"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=True
    )
    salient_moment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("salient_moments.id"), nullable=True)
    source_buffer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_memory_buffers.id"), nullable=True)
    source_buffer_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_memory_buffer_items.id"), nullable=True
    )
    proposed_shared_memory_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_memory_candidates.id"), nullable=True
    )
    candidate_status: Mapped[str] = mapped_column(Text, default="pending_review")
    candidate_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_user_review: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_commit_shared_memory: Mapped[bool] = mapped_column(Boolean, default=False)
    shared_to_private_policy: Mapped[str] = mapped_column(Text, default="review_required")
    private_to_shared_policy: Mapped[str] = mapped_column(Text, default="review_required")
    candidate_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class RealtimeMemoryExpiryEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "realtime_memory_expiry_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    buffer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_memory_buffers.id"), nullable=True)
    buffer_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_memory_buffer_items.id"), nullable=True
    )
    salient_moment_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("salient_moments.id"), nullable=True)
    expiry_status: Mapped[str] = mapped_column(Text, default="scheduled")
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_data_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    expiry_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


__all__ = [
    "RealtimeMemoryBuffer",
    "RealtimeMemoryBufferItem",
    "CompanionPrivateRealtimeBuffer",
    "CoPresenceSessionBuffer",
    "SharedSceneBuffer",
    "SalientMoment",
    "CompanionPrivateSalientMoment",
    "SharedSalientMoment",
    "RealtimeSharedMemoryCandidate",
    "RealtimeMemoryExpiryEvent",
]
