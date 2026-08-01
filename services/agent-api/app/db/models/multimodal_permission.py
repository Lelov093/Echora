"""Realtime compatibility multimodal context and permission ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class MultimodalContextEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "multimodal_context_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=True
    )
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    shared_scene_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("shared_scenes.id"), nullable=True)
    source_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_participants.id"), nullable=True
    )
    context_type: Mapped[str] = mapped_column(Text, nullable=False)
    context_source: Mapped[str] = mapped_column(Text, default="manual_user_action")
    context_status: Mapped[str] = mapped_column(Text, default="created")
    raw_data_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_data_retention_policy: Mapped[str] = mapped_column(Text, default="ephemeral")
    raw_data_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    permission_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    visibility_summary_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    redaction_status: Mapped[str] = mapped_column(Text, default="pending")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ImageContextEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "image_context_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    context_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("multimodal_context_events.id"), nullable=False)
    image_context_kind: Mapped[str] = mapped_column(Text, default="user_uploaded_image")
    image_count: Mapped[int] = mapped_column(Integer, default=1)
    image_ref_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    image_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class ScreenContextEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "screen_context_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    context_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("multimodal_context_events.id"), nullable=False)
    screen_context_kind: Mapped[str] = mapped_column(Text, default="manual_screenshot")
    window_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    screen_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    capture_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_manual_user_action: Mapped[bool] = mapped_column(Boolean, default=True)


class FileContextRealtimeEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "file_context_realtime_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    context_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("multimodal_context_events.id"), nullable=False)
    file_context_kind: Mapped[str] = mapped_column(Text, default="user_selected_file")
    file_document_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("file_documents.id"), nullable=True)
    file_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_mime_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    excerpt_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_summary: Mapped[str | None] = mapped_column(Text, nullable=True)


class DeviceContextEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "device_context_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    context_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("multimodal_context_events.id"), nullable=False)
    device_event_kind: Mapped[str] = mapped_column(Text, default="manual_device_status")
    device_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_manual_user_action: Mapped[bool] = mapped_column(Boolean, default=True)
    device_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ParticipantContextPermission(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "participant_context_permissions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    context_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("multimodal_context_events.id"), nullable=False)
    realtime_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=True
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_participants.id"), nullable=False
    )
    permission_source: Mapped[str] = mapped_column(Text, default="user_grant")
    can_see: Mapped[bool] = mapped_column(Boolean, default=True)
    can_use: Mapped[bool] = mapped_column(Boolean, default=True)
    can_remember: Mapped[bool] = mapped_column(Boolean, default=False)
    can_view_raw_data: Mapped[bool] = mapped_column(Boolean, default=False)
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    permission_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    boundary_policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ContextRetentionPolicy(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "context_retention_policies"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    context_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("multimodal_context_events.id"), nullable=True)
    realtime_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=True
    )
    policy_scope: Mapped[str] = mapped_column(Text, default="context_event")
    retention_policy: Mapped[str] = mapped_column(Text, default="ephemeral")
    redaction_status: Mapped[str] = mapped_column(Text, default="pending")
    raw_data_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class EphemeralContextExpiryEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "ephemeral_context_expiry_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    context_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("multimodal_context_events.id"), nullable=True)
    retention_policy_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("context_retention_policies.id"), nullable=True)
    expiry_status: Mapped[str] = mapped_column(Text, default="scheduled")
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raw_data_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    redaction_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    expiry_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


__all__ = [
    "MultimodalContextEvent",
    "ImageContextEvent",
    "ScreenContextEvent",
    "FileContextRealtimeEvent",
    "DeviceContextEvent",
    "ParticipantContextPermission",
    "ContextRetentionPolicy",
    "EphemeralContextExpiryEvent",
]
