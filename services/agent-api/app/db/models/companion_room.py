"""Durable Companion Room membership and Discord channel mapping truth."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class CompanionRoomMembershipEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_room_membership_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    co_presence_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=False
    )
    participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_participants.id"), nullable=True
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    from_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    roster_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    participant_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class CompanionRoomTurn(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    """One durable owner-authored turn in a persistent Companion Room."""

    __tablename__ = "companion_room_turns"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    co_presence_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    user_message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(32), default="web", nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="planning", nullable=False)
    cancellation_requested: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    speaker_plan_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    result_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    error_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CompanionRoomTurnStep(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    """Independent Companion execution and evidence for a Room turn."""

    __tablename__ = "companion_room_turn_steps"

    room_turn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companion_room_turns.id"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    participant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_participants.id"), nullable=False
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="planned", nullable=False)
    selection_reason: Mapped[str] = mapped_column(String(80), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True)
    assistant_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True)
    evidence_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    error_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    retry_available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DiscordGuild(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "discord_guilds"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_providers.id"), nullable=False)
    provider_guild_ref: Mapped[str] = mapped_column(Text, nullable=False)
    provider_guild_ref_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    guild_display_name: Mapped[str] = mapped_column(Text, nullable=False)
    guild_status: Mapped[str] = mapped_column(Text, default="active", nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class DiscordTextChannel(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "discord_text_channels"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    discord_guild_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("discord_guilds.id"), nullable=False)
    provider_channel_ref: Mapped[str] = mapped_column(Text, nullable=False)
    provider_channel_ref_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    channel_display_name: Mapped[str] = mapped_column(Text, nullable=False)
    channel_status: Mapped[str] = mapped_column(Text, default="active", nullable=False)
    permission_status: Mapped[str] = mapped_column(Text, default="unverified", nullable=False)
    permission_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class DiscordChannelBotMembership(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "discord_channel_bot_memberships"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    discord_text_channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discord_text_channels.id"), nullable=False
    )
    discord_channel_room_binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discord_channel_room_bindings.id"), nullable=False
    )
    provider_bot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=False
    )
    companion_channel_identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companion_channel_identities.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    participation_mode: Mapped[str] = mapped_column(Text, default="mention_only", nullable=False)
    membership_status: Mapped[str] = mapped_column(Text, default="active", nullable=False)
    identity_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DiscordChannelRoomBinding(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "discord_channel_room_bindings"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    discord_text_channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discord_text_channels.id"), nullable=False
    )
    co_presence_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=False
    )
    binding_status: Mapped[str] = mapped_column(Text, default="active", nullable=False)
    mention_policy: Mapped[str] = mapped_column(Text, default="mention_only", nullable=False)
    roster_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    room_roster_revision: Mapped[int] = mapped_column(Integer, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class DiscordChannelIngress(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    """One provider Channel message claimed once across every physical Bot."""

    __tablename__ = "discord_channel_ingresses"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    discord_channel_room_binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discord_channel_room_bindings.id"), nullable=False
    )
    discord_text_channel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discord_text_channels.id"), nullable=False
    )
    co_presence_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    room_turn_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companion_room_turns.id"), nullable=True
    )
    user_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=True
    )
    provider_guild_ref_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_channel_ref_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_message_ref_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    external_author_ref_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    author_display_name: Mapped[str] = mapped_column(String(200), default="Discord user", nullable=False)
    observed_bot_key: Mapped[str] = mapped_column(String(120), nullable=False)
    ingress_status: Mapped[str] = mapped_column(String(32), default="received", nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    mentioned_bot_keys_json: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    selected_companion_ids_json: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    evidence_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    error_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DiscordChannelDelivery(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    """Durable correct-Bot Channel outbox for one completed Room Turn Step."""

    __tablename__ = "discord_channel_deliveries"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    discord_channel_ingress_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discord_channel_ingresses.id"), nullable=False
    )
    discord_channel_room_binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discord_channel_room_bindings.id"), nullable=False
    )
    room_turn_step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companion_room_turn_steps.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    provider_bot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=False
    )
    assistant_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False
    )
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True
    )
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(160), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_message_ref_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    last_error_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = [
    "CompanionRoomMembershipEvent",
    "CompanionRoomTurn",
    "CompanionRoomTurnStep",
    "DiscordGuild",
    "DiscordTextChannel",
    "DiscordChannelBotMembership",
    "DiscordChannelRoomBinding",
    "DiscordChannelIngress",
    "DiscordChannelDelivery",
]
