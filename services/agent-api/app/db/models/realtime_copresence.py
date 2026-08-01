"""Realtime compatibility realtime co-presence ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class RealtimeCoPresenceSession(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "realtime_copresence_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    active_companion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True
    )
    originating_conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    shared_scene_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("shared_scenes.id"), nullable=True)
    session_title: Mapped[str] = mapped_column(Text, default="")
    session_status: Mapped[str] = mapped_column(Text, default="created")
    session_source: Mapped[str] = mapped_column(Text, default="conversation")
    default_transport: Mapped[str] = mapped_column(Text, default="sse")
    permission_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    participant_summary_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    boundary_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    runtime_state_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RealtimeCoPresenceParticipant(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "realtime_copresence_participants"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=False
    )
    co_presence_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_participants.id"), nullable=True
    )
    participant_type: Mapped[str] = mapped_column(Text, nullable=False)
    participant_role: Mapped[str] = mapped_column(Text, default="listener_companion")
    participant_status: Mapped[str] = mapped_column(Text, default="active")
    participant_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    participant_companion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True
    )
    external_agent_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    can_listen: Mapped[bool] = mapped_column(Boolean, default=False)
    can_speak: Mapped[bool] = mapped_column(Boolean, default=False)
    can_observe: Mapped[bool] = mapped_column(Boolean, default=True)
    can_remember: Mapped[bool] = mapped_column(Boolean, default=False)
    can_receive_transcript: Mapped[bool] = mapped_column(Boolean, default=False)
    permission_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    runtime_state_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RealtimeParticipantState(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "realtime_participant_states"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=False
    )
    realtime_participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_participants.id"), nullable=False
    )
    state_type: Mapped[str] = mapped_column(Text, default="presence")
    state_status: Mapped[str] = mapped_column(Text, default="active")
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)
    can_listen: Mapped[bool] = mapped_column(Boolean, default=False)
    can_speak: Mapped[bool] = mapped_column(Boolean, default=False)
    can_observe: Mapped[bool] = mapped_column(Boolean, default=True)
    can_remember: Mapped[bool] = mapped_column(Boolean, default=False)
    state_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    permission_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RealtimeSessionChannel(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "realtime_session_channels"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=False
    )
    channel_type: Mapped[str] = mapped_column(Text, default="sse")
    channel_status: Mapped[str] = mapped_column(Text, default="active")
    transport_type: Mapped[str] = mapped_column(Text, default="sse")
    is_default_event_stream: Mapped[bool] = mapped_column(Boolean, default=True)
    can_send_events: Mapped[bool] = mapped_column(Boolean, default=True)
    can_receive_actions: Mapped[bool] = mapped_column(Boolean, default=False)
    permission_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    runtime_state_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RealtimeSessionStateEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "realtime_session_state_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=False
    )
    actor_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_participants.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_status: Mapped[str] = mapped_column(Text, default="recorded")
    previous_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    permission_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RealtimeChannelStateEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "realtime_channel_state_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=False
    )
    channel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_session_channels.id"), nullable=False)
    actor_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_participants.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_status: Mapped[str] = mapped_column(Text, default="recorded")
    previous_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    next_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    event_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    permission_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = [
    "RealtimeCoPresenceSession",
    "RealtimeCoPresenceParticipant",
    "RealtimeParticipantState",
    "RealtimeSessionChannel",
    "RealtimeSessionStateEvent",
    "RealtimeChannelStateEvent",
]
