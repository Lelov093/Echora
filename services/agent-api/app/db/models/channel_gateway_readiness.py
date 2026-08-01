"""Realtime compatibility channel gateway readiness ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class PresenceChannelBinding(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "presence_channel_bindings"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True)
    realtime_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=True
    )
    binding_status: Mapped[str] = mapped_column(Text, default="draft")
    channel_kind: Mapped[str] = mapped_column(Text, default="readiness_stub")
    connector_kind: Mapped[str] = mapped_column(Text, default="readiness_stub")
    external_channel_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_channel_ref_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    stores_plaintext_token: Mapped[bool] = mapped_column(Boolean, default=False)
    credentials_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    can_receive_inbound: Mapped[bool] = mapped_column(Boolean, default=False)
    can_send_outbound: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_user_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    readiness_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    permission_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    boundary_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class CompanionChannelIdentity(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_channel_identities"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    presence_channel_binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presence_channel_bindings.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    identity_status: Mapped[str] = mapped_column(Text, default="draft")
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_identity_ref_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    persona_projection_policy: Mapped[str] = mapped_column(Text, default="summary_only")
    can_present_companion_identity: Mapped[bool] = mapped_column(Boolean, default=False)
    can_autonomously_message: Mapped[bool] = mapped_column(Boolean, default=False)
    identity_profile_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    channel_binding_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=True)
    provider_bot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=True)
    # Persisted compatibility value constrained by the existing database contract.
    identity_scope: Mapped[str] = mapped_column(Text, default="mock_projection")
    channel_status: Mapped[str] = mapped_column(Text, default="draft")
    channel_display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_avatar_placeholder: Mapped[str | None] = mapped_column(Text, nullable=True)
    channel_persona_projection: Mapped[str] = mapped_column(Text, default="")
    channel_persona_projection_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    channel_presence_style: Mapped[str] = mapped_column(Text, default="inherit_companion")
    channel_boundary_profile: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    persona_projection_mode: Mapped[str] = mapped_column(Text, default="summary_only")
    private_memory_visible_by_default: Mapped[bool] = mapped_column(Boolean, default=False)
    uses_single_global_bot_gateway: Mapped[bool] = mapped_column(Boolean, default=False)
    is_global_bot_identity: Mapped[bool] = mapped_column(Boolean, default=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)


class ChannelPermissionPolicy(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_permission_policies"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    presence_channel_binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presence_channel_bindings.id"), nullable=False
    )
    policy_status: Mapped[str] = mapped_column(Text, default="draft")
    inbound_policy: Mapped[str] = mapped_column(Text, default="disabled")
    outbound_policy: Mapped[str] = mapped_column(Text, default="disabled")
    inbound_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    outbound_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_user_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    allows_memory_read: Mapped[bool] = mapped_column(Boolean, default=False)
    allows_memory_write: Mapped[bool] = mapped_column(Boolean, default=False)
    allows_raw_attachment_storage: Mapped[bool] = mapped_column(Boolean, default=False)
    allows_unsolicited_message: Mapped[bool] = mapped_column(Boolean, default=False)
    permission_policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ChannelMessageEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_message_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    presence_channel_binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presence_channel_bindings.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True)
    realtime_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=True
    )
    channel_permission_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_permission_policies.id"), nullable=True
    )
    message_direction: Mapped[str] = mapped_column(Text, nullable=False)
    message_status: Mapped[str] = mapped_column(Text, default="queued")
    message_summary: Mapped[str] = mapped_column(Text, default="")
    raw_message_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_message_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    memory_candidate_policy: Mapped[str] = mapped_column(Text, default="review_required")
    requires_user_review: Mapped[bool] = mapped_column(Boolean, default=True)
    redaction_status: Mapped[str] = mapped_column(Text, default="pending")
    message_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channel_binding_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=True)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_providers.id"), nullable=True)
    provider_bot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=True)
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True)
    external_message_ref_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_conversation_ref_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_is_ephemeral: Mapped[bool] = mapped_column(Boolean, default=True)
    raw_payload_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    safe_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ChannelMemoryBoundaryPolicy(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_memory_boundary_policies"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    presence_channel_binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presence_channel_bindings.id"), nullable=False
    )
    policy_status: Mapped[str] = mapped_column(Text, default="draft")
    memory_read_scope: Mapped[str] = mapped_column(Text, default="none")
    memory_write_policy: Mapped[str] = mapped_column(Text, default="deny")
    private_memory_access_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    shared_memory_write_requires_review: Mapped[bool] = mapped_column(Boolean, default=True)
    cross_companion_memory_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_message_to_memory_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    boundary_policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    channel_binding_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=True)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_providers.id"), nullable=True)
    ephemeral_by_default: Mapped[bool] = mapped_column(Boolean, default=True)
    review_required_for_memory_write: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_write_allowed: Mapped[bool] = mapped_column(Boolean, default=False)


class ChannelAuditEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_audit_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    presence_channel_binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presence_channel_bindings.id"), nullable=False
    )
    channel_message_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_message_events.id"), nullable=True)
    audit_event_type: Mapped[str] = mapped_column(Text, default="created")
    audit_status: Mapped[str] = mapped_column(Text, default="recorded")
    audit_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelRevokeEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_revoke_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    presence_channel_binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presence_channel_bindings.id"), nullable=False
    )
    revoke_status: Mapped[str] = mapped_column(Text, default="requested")
    revoke_scope: Mapped[str] = mapped_column(Text, default="all")
    revokes_credentials_ref: Mapped[bool] = mapped_column(Boolean, default=True)
    stops_inbound: Mapped[bool] = mapped_column(Boolean, default=True)
    stops_outbound: Mapped[bool] = mapped_column(Boolean, default=True)
    audit_required: Mapped[bool] = mapped_column(Boolean, default=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    revoke_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    channel_binding_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=True)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_providers.id"), nullable=True)
    provider_bot_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=True)
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True)
    stops_checkins: Mapped[bool] = mapped_column(Boolean, default=True)
    clears_ephemeral_buffer: Mapped[bool] = mapped_column(Boolean, default=True)
    disables_memory_candidates: Mapped[bool] = mapped_column(Boolean, default=True)


__all__ = [
    "PresenceChannelBinding",
    "CompanionChannelIdentity",
    "ChannelPermissionPolicy",
    "ChannelMessageEvent",
    "ChannelMemoryBoundaryPolicy",
    "ChannelAuditEvent",
    "ChannelRevokeEvent",
]
