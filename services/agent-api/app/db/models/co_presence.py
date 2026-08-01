"""Companion co-presence ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class CoPresenceSession(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "co_presence_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    primary_companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    originating_conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    session_title: Mapped[str] = mapped_column(Text, default="")
    session_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    session_status: Mapped[str] = mapped_column(Text, default="active")
    session_source: Mapped[str] = mapped_column(Text, default="direct_conversation")
    visibility_scope: Mapped[str] = mapped_column(Text, default="role_summary")
    entry_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    participant_summary_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    boundary_summary_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    roster_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class CoPresenceParticipant(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "co_presence_participants"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    co_presence_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=False
    )
    participant_type: Mapped[str] = mapped_column(Text, nullable=False)
    participant_role: Mapped[str] = mapped_column(Text, default="active_companion")
    participant_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    participant_companion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True
    )
    external_agent_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    join_status: Mapped[str] = mapped_column(Text, default="active")
    visibility_scope: Mapped[str] = mapped_column(Text, default="role_summary")
    can_speak: Mapped[bool] = mapped_column(Boolean, default=True)
    can_delegate: Mapped[bool] = mapped_column(Boolean, default=False)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejoined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    muted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    membership_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    policy_override_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class CoPresenceSessionPolicy(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "co_presence_session_policies"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    co_presence_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=False
    )
    policy_status: Mapped[str] = mapped_column(Text, default="active")
    default_primary_memory_participation: Mapped[str] = mapped_column(Text, default="private_candidate_allowed")
    default_active_memory_participation: Mapped[str] = mapped_column(Text, default="shared_candidate_allowed")
    default_observing_memory_participation: Mapped[str] = mapped_column(Text, default="none")
    default_delegated_memory_participation: Mapped[str] = mapped_column(Text, default="candidate_only")
    user_global_memory_scope: Mapped[str] = mapped_column(Text, default="low_risk_summary_only")
    cross_companion_private_read_policy: Mapped[str] = mapped_column(Text, default="deny")
    private_to_shared_policy: Mapped[str] = mapped_column(Text, default="review_required")
    shared_to_private_policy: Mapped[str] = mapped_column(Text, default="review_required")
    allow_observing_companion_long_term_memory: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_autonomous_companion_interaction: Mapped[bool] = mapped_column(Boolean, default=False)
    session_visibility_policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    boundary_policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ParticipantAwarenessState(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "participant_awareness_states"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    co_presence_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=False
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_participants.id"), nullable=False
    )
    target_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_participants.id"), nullable=True
    )
    awareness_type: Mapped[str] = mapped_column(Text, default="participant_presence")
    awareness_level: Mapped[str] = mapped_column(Text, default="full")
    awareness_status: Mapped[str] = mapped_column(Text, default="active")
    updated_by_source: Mapped[str] = mapped_column(Text, default="system")
    awareness_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    awareness_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ParticipantMemoryPermission(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "participant_memory_permissions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    co_presence_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=False
    )
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_participants.id"), nullable=False
    )
    permission_source: Mapped[str] = mapped_column(Text, default="session_default")
    memory_participation_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    allow_private_candidate: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    allow_shared_candidate: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    allow_user_global_summary_read: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    allow_user_global_full_read: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    allow_cross_companion_private_read: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    allow_private_to_shared_sync: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    allow_shared_to_private_sync: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    boundary_policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


__all__ = [
    "CoPresenceSession",
    "CoPresenceParticipant",
    "CoPresenceSessionPolicy",
    "ParticipantAwarenessState",
    "ParticipantMemoryPermission",
]
