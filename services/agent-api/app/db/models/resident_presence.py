"""Realtime compatibility resident presence and hard-stop ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class CompanionResidentStatusEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_resident_status_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    realtime_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=True
    )
    status_type: Mapped[str] = mapped_column(Text, default="available")
    status_source: Mapped[str] = mapped_column(Text, default="system")
    interruption_level: Mapped[str] = mapped_column(Text, default="low")
    allows_unsolicited_presence: Mapped[bool] = mapped_column(Boolean, default=False)
    presence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CompanionPresenceBudget(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_presence_budgets"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    budget_scope: Mapped[str] = mapped_column(Text, default="daily")
    budget_status: Mapped[str] = mapped_column(Text, default="active")
    enforcement_policy: Mapped[str] = mapped_column(Text, default="queue")
    max_presence_minutes: Mapped[int] = mapped_column(Integer, default=0)
    used_presence_minutes: Mapped[int] = mapped_column(Integer, default=0)
    max_interruptions: Mapped[int] = mapped_column(Integer, default=0)
    used_interruptions: Mapped[int] = mapped_column(Integer, default=0)
    window_starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    budget_policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class CoPresenceInvitation(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "copresence_invitations"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    realtime_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=True
    )
    inviter_companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True)
    target_companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    invitation_status: Mapped[str] = mapped_column(Text, default="queued")
    invitation_source: Mapped[str] = mapped_column(Text, default="user")
    requires_user_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_join_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    memory_candidate_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    invitation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QuietHourSetting(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "quiet_hour_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True)
    quiet_status: Mapped[str] = mapped_column(Text, default="active")
    quiet_policy: Mapped[str] = mapped_column(Text, default="queue")
    day_of_week: Mapped[int | None] = mapped_column(Integer, nullable=True)
    start_minute: Mapped[int] = mapped_column(Integer, default=0)
    end_minute: Mapped[int] = mapped_column(Integer, default=0)
    timezone: Mapped[str] = mapped_column(Text, default="UTC")
    allows_emergency_override: Mapped[bool] = mapped_column(Boolean, default=False)
    policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class FocusModeEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "focus_mode_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True)
    realtime_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=True
    )
    focus_status: Mapped[str] = mapped_column(Text, default="active")
    focus_scope: Mapped[str] = mapped_column(Text, default="all_realtime")
    suppress_presence: Mapped[bool] = mapped_column(Boolean, default=True)
    suppress_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_critical_only: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    policy_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ResidentPresenceEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "resident_presence_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    realtime_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(Text, default="ambient_status")
    event_status: Mapped[str] = mapped_column(Text, default="queued")
    interruption_level: Mapped[str] = mapped_column(Text, default="low")
    requires_user_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_surface: Mapped[str] = mapped_column(Text, default="presence_page")
    event_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ScopedHardStopEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "scoped_hard_stop_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    hard_stop_scope: Mapped[str] = mapped_column(Text, nullable=False)
    hard_stop_status: Mapped[str] = mapped_column(Text, default="active")
    initiated_by: Mapped[str] = mapped_column(Text, default="user")
    realtime_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=True
    )
    channel_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_session_channels.id"), nullable=True)
    companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True)
    context_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("multimodal_context_events.id"), nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    stops_listening: Mapped[bool] = mapped_column(Boolean, default=True)
    stops_speaking: Mapped[bool] = mapped_column(Boolean, default=True)
    stops_observing: Mapped[bool] = mapped_column(Boolean, default=True)
    stops_memory_capture: Mapped[bool] = mapped_column(Boolean, default=True)
    stops_context_capture: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_audit: Mapped[bool] = mapped_column(Boolean, default=True)
    policy_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class HardStopAuditEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "hard_stop_audit_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    hard_stop_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("scoped_hard_stop_events.id"), nullable=False)
    audit_event_type: Mapped[str] = mapped_column(Text, default="created")
    audit_status: Mapped[str] = mapped_column(Text, default="recorded")
    affected_scope: Mapped[str] = mapped_column(Text, nullable=False)
    affected_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_participants.id"), nullable=True
    )
    audit_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = [
    "CompanionResidentStatusEvent",
    "CompanionPresenceBudget",
    "CoPresenceInvitation",
    "QuietHourSetting",
    "FocusModeEvent",
    "ResidentPresenceEvent",
    "ScopedHardStopEvent",
    "HardStopAuditEvent",
]
