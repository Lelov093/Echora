"""Channel Gateway Companion Channel Gateway ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class ChannelProvider(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_providers"

    provider_key: Mapped[str] = mapped_column(Text, nullable=False)
    provider_display_name: Mapped[str] = mapped_column(Text, nullable=False)
    provider_kind: Mapped[str] = mapped_column(Text, nullable=False)
    provider_status: Mapped[str] = mapped_column(Text, default="available")
    is_real_provider: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_multi_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_inbound: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_outbound: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_low_frequency_checkin: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_external_token: Mapped[bool] = mapped_column(Boolean, default=False)
    config_schema_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ChannelProviderConfig(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_provider_configs"

    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_providers.id"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    config_status: Mapped[str] = mapped_column(Text, default="draft")
    secret_policy: Mapped[str] = mapped_column(Text, default="token_secret_ref_only")
    stores_plaintext_token: Mapped[bool] = mapped_column(Boolean, default=False)
    provider_config_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    safe_public_config_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ChannelBotRegistry(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_bot_registries"

    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_providers.id"), nullable=False)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    bot_key: Mapped[str] = mapped_column(Text, nullable=False)
    bot_display_name: Mapped[str] = mapped_column(Text, nullable=False)
    bot_status: Mapped[str] = mapped_column(Text, default="draft")
    token_status: Mapped[str] = mapped_column(Text, default="missing")
    token_secret_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    stores_plaintext_token: Mapped[bool] = mapped_column(Boolean, default=False)
    external_application_id_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_bot_user_id_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    safe_metadata_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ChannelBinding(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_bindings"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_providers.id"), nullable=False)
    provider_bot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=True
    )
    presence_channel_binding_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presence_channel_bindings.id"), nullable=True
    )
    binding_status: Mapped[str] = mapped_column(Text, default="draft")
    binding_scope: Mapped[str] = mapped_column(Text, default="dm")
    permission_scope: Mapped[str] = mapped_column(Text, default="reply_only")
    outbound_policy: Mapped[str] = mapped_column(Text, default="reply_only")
    memory_policy: Mapped[str] = mapped_column(Text, default="ephemeral_review_gated")
    requires_user_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    can_receive_inbound: Mapped[bool] = mapped_column(Boolean, default=False)
    can_send_outbound: Mapped[bool] = mapped_column(Boolean, default=False)
    checkin_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    memory_write_requires_review: Mapped[bool] = mapped_column(Boolean, default=True)
    raw_message_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    stores_plaintext_token: Mapped[bool] = mapped_column(Boolean, default=False)
    external_channel_ref_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_user_ref_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_guild_ref_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    external_thread_ref_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    permission_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    boundary_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelWebhookEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_webhook_events"

    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_providers.id"), nullable=False)
    provider_bot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=True
    )
    channel_binding_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=True)
    channel_message_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_message_events.id"), nullable=True
    )
    webhook_event_type: Mapped[str] = mapped_column(Text, nullable=False)
    webhook_status: Mapped[str] = mapped_column(Text, default="received")
    external_event_ref_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_summary: Mapped[str] = mapped_column(Text, default="")
    raw_payload_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    safe_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelDeliveryEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_delivery_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    channel_binding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=False)
    channel_message_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_message_events.id"), nullable=True
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_providers.id"), nullable=False)
    provider_bot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=True
    )
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True)
    delivery_status: Mapped[str] = mapped_column(Text, default="queued")
    delivery_mode: Mapped[str] = mapped_column(Text, default="reply_only")
    delivery_attempt: Mapped[int] = mapped_column(Integer, default=1)
    external_delivery_ref_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_summary: Mapped[str] = mapped_column(Text, default="")
    raw_payload_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    safe_delivery_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    queued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelRateLimitEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_rate_limit_events"

    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_providers.id"), nullable=False)
    provider_bot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=True
    )
    channel_binding_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=True)
    rate_limit_status: Mapped[str] = mapped_column(Text, default="active")
    retry_after_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    limit_scope_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    safe_rate_limit_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelFailureEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_failure_events"

    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_providers.id"), nullable=False)
    provider_bot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=True
    )
    channel_binding_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=True)
    channel_message_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_message_events.id"), nullable=True
    )
    channel_delivery_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_delivery_events.id"), nullable=True
    )
    failure_type: Mapped[str] = mapped_column(Text, default="unknown")
    failure_status: Mapped[str] = mapped_column(Text, default="recorded")
    safe_error_summary: Mapped[str] = mapped_column(Text, default="")
    safe_error_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DiscordDmConversationBinding(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    """Durable Discord DM to Single-Companion Conversation binding.

    Provider references are runtime-only routing identifiers. They are never
    projected by the public API; public projections expose hashes only.
    """

    __tablename__ = "discord_dm_conversation_bindings"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    provider_bot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=False
    )
    companion_channel_identity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companion_channel_identities.id"), nullable=False
    )
    channel_binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    external_user_ref_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    external_channel_ref_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_channel_ref: Mapped[str] = mapped_column(Text, nullable=False)
    binding_status: Mapped[str] = mapped_column(Text, default="active", nullable=False)
    binding_source: Mapped[str] = mapped_column(Text, default="first_dm", nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_inbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_outbound_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DiscordDmDelivery(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    """Durable, retryable Discord reply outbox linked to a persisted message."""

    __tablename__ = "discord_dm_deliveries"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    dm_binding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("discord_dm_conversation_bindings.id"), nullable=False
    )
    channel_delivery_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_delivery_events.id"), nullable=True
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    assistant_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False
    )
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True
    )
    inbound_message_ref_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)
    delivery_status: Mapped[str] = mapped_column(Text, default="queued", nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(Text, nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider_message_ref_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelEphemeralBuffer(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_ephemeral_buffers"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    channel_binding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=False)
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_providers.id"), nullable=False)
    provider_bot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=True
    )
    buffer_status: Mapped[str] = mapped_column(Text, default="active")
    retention_seconds: Mapped[int] = mapped_column(Integer, default=86400)
    raw_payload_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    memory_candidate_generation_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    safe_buffer_summary: Mapped[str] = mapped_column(Text, default="")
    buffer_policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelEphemeralBufferItem(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_ephemeral_buffer_items"

    channel_ephemeral_buffer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_ephemeral_buffers.id"), nullable=False
    )
    channel_message_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_message_events.id"), nullable=True
    )
    buffer_item_status: Mapped[str] = mapped_column(Text, default="active")
    safe_content_summary: Mapped[str] = mapped_column(Text, default="")
    salience_score: Mapped[float] = mapped_column(Float, default=0.0)
    raw_payload_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    long_term_memory_written: Mapped[bool] = mapped_column(Boolean, default=False)
    safe_item_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelMemoryCandidate(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_memory_candidates"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    channel_binding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=False)
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_providers.id"), nullable=False)
    provider_bot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=True
    )
    channel_message_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_message_events.id"), nullable=True
    )
    channel_ephemeral_buffer_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_ephemeral_buffer_items.id"), nullable=True
    )
    candidate_status: Mapped[str] = mapped_column(Text, default="pending_review")
    target_memory_scope: Mapped[str] = mapped_column(Text, default="companion_private")
    candidate_summary: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_memory_content: Mapped[str] = mapped_column(Text, default="")
    salience_score: Mapped[float] = mapped_column(Float, default=0.0)
    requires_user_review: Mapped[bool] = mapped_column(Boolean, default=True)
    auto_commit_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_payload_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    safe_evidence_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ChannelMemoryReview(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_memory_reviews"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    channel_memory_candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_memory_candidates.id"), nullable=False
    )
    review_decision: Mapped[str] = mapped_column(Text, default="pending")
    target_memory_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id"), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    memory_write_allowed_after_review: Mapped[bool] = mapped_column(Boolean, default=False)
    safe_review_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelContextRedactionEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_context_redaction_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    channel_binding_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=True)
    channel_message_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_message_events.id"), nullable=True
    )
    channel_ephemeral_buffer_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_ephemeral_buffer_items.id"), nullable=True
    )
    channel_memory_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_memory_candidates.id"), nullable=True
    )
    redaction_scope: Mapped[str] = mapped_column(Text, nullable=False)
    redaction_status: Mapped[str] = mapped_column(Text, default="requested")
    redaction_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    safe_redaction_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelPresencePolicy(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_presence_policies"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    channel_binding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=False)
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_providers.id"), nullable=False)
    provider_bot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=True
    )
    policy_status: Mapped[str] = mapped_column(Text, default="draft")
    presence_mode: Mapped[str] = mapped_column(Text, default="reply_only")
    reply_only_default: Mapped[bool] = mapped_column(Boolean, default=True)
    low_frequency_checkin_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    channel_mute: Mapped[bool] = mapped_column(Boolean, default=False)
    outbound_disabled: Mapped[bool] = mapped_column(Boolean, default=False)
    daily_presence_budget: Mapped[int] = mapped_column(Integer, default=0)
    remaining_presence_budget: Mapped[int] = mapped_column(Integer, default=0)
    quiet_hours_enforced: Mapped[bool] = mapped_column(Boolean, default=True)
    focus_mode_enforced: Mapped[bool] = mapped_column(Boolean, default=True)
    meaningful_silence_enforced: Mapped[bool] = mapped_column(Boolean, default=True)
    policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ChannelCheckinSetting(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_checkin_settings"

    channel_presence_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_presence_policies.id"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    frequency: Mapped[str] = mapped_column(Text, default="manual")
    min_interval_seconds: Mapped[int] = mapped_column(Integer, default=86400)
    requires_user_opt_in: Mapped[bool] = mapped_column(Boolean, default=True)
    quiet_hours_enforced: Mapped[bool] = mapped_column(Boolean, default=True)
    focus_mode_enforced: Mapped[bool] = mapped_column(Boolean, default=True)
    presence_budget_enforced: Mapped[bool] = mapped_column(Boolean, default=True)
    meaningful_silence_enforced: Mapped[bool] = mapped_column(Boolean, default=True)
    next_eligible_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settings_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class ChannelPresenceBudgetEvent(Base, UUIDMixin, MetadataMixin):
    __tablename__ = "channel_presence_budget_events"

    channel_presence_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_presence_policies.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    budget_delta: Mapped[int] = mapped_column(Integer, default=0)
    remaining_budget: Mapped[int] = mapped_column(Integer, default=0)
    event_summary: Mapped[str] = mapped_column(Text, default="")
    event_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelQuietHourRule(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_quiet_hour_rules"

    channel_presence_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_presence_policies.id"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    timezone: Mapped[str] = mapped_column(Text, default="UTC")
    start_minute_of_day: Mapped[int] = mapped_column(Integer, nullable=False)
    end_minute_of_day: Mapped[int] = mapped_column(Integer, nullable=False)
    applies_to_checkins: Mapped[bool] = mapped_column(Boolean, default=True)
    applies_to_outbound: Mapped[bool] = mapped_column(Boolean, default=True)


class ChannelFocusModeRule(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "channel_focus_mode_rules"

    channel_presence_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_presence_policies.id"), nullable=False
    )
    focus_status: Mapped[str] = mapped_column(Text, default="inactive")
    suppresses_outbound: Mapped[bool] = mapped_column(Boolean, default=True)
    suppresses_checkins: Mapped[bool] = mapped_column(Boolean, default=True)
    focus_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ChannelMeaningfulSilenceEvent(Base, UUIDMixin, MetadataMixin):
    __tablename__ = "channel_meaningful_silence_events"

    channel_presence_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_presence_policies.id"), nullable=False
    )
    silence_reason: Mapped[str] = mapped_column(Text, nullable=False)
    suppressed_outbound_count: Mapped[int] = mapped_column(Integer, default=0)
    silence_summary: Mapped[str] = mapped_column(Text, default="")
    event_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelOutboundSuppressionEvent(Base, UUIDMixin, MetadataMixin):
    __tablename__ = "channel_outbound_suppression_events"

    channel_presence_policy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_presence_policies.id"), nullable=False
    )
    channel_delivery_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_delivery_events.id"), nullable=True
    )
    suppression_reason: Mapped[str] = mapped_column(Text, nullable=False)
    suppression_status: Mapped[str] = mapped_column(Text, default="applied")
    suppression_summary: Mapped[str] = mapped_column(Text, default="")
    safe_suppression_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelTraceEvent(Base, UUIDMixin, MetadataMixin):
    __tablename__ = "channel_trace_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True)
    channel_binding_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=True)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_providers.id"), nullable=True)
    provider_bot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=True
    )
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True)
    channel_message_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_message_events.id"), nullable=True
    )
    channel_delivery_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_delivery_events.id"), nullable=True
    )
    trace_event_type: Mapped[str] = mapped_column(Text, nullable=False)
    trace_status: Mapped[str] = mapped_column(Text, default="recorded")
    trace_summary: Mapped[str] = mapped_column(Text, default="")
    safe_trace_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelAuditLog(Base, UUIDMixin, MetadataMixin):
    __tablename__ = "channel_audit_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    channel_binding_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=True)
    provider_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_providers.id"), nullable=True)
    provider_bot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=True
    )
    channel_trace_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_trace_events.id"), nullable=True
    )
    audit_log_type: Mapped[str] = mapped_column(Text, nullable=False)
    audit_summary: Mapped[str] = mapped_column(Text, default="")
    safe_audit_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelBindingStatusEvent(Base, UUIDMixin, MetadataMixin):
    __tablename__ = "channel_binding_status_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    channel_binding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=False)
    status_event: Mapped[str] = mapped_column(Text, nullable=False)
    from_status: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_status: Mapped[str] = mapped_column(Text, nullable=False)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    safe_status_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelOutboundAuditEvent(Base, UUIDMixin, MetadataMixin):
    __tablename__ = "channel_outbound_audit_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    channel_binding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=False)
    channel_delivery_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_delivery_events.id"), nullable=True
    )
    channel_message_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_message_events.id"), nullable=True
    )
    provider_bot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_bot_registries.id"), nullable=True
    )
    outbound_audit_status: Mapped[str] = mapped_column(Text, nullable=False)
    outbound_policy_snapshot: Mapped[str] = mapped_column(Text, default="reply_only")
    audit_summary: Mapped[str] = mapped_column(Text, default="")
    safe_outbound_audit_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ChannelMemoryGateTrace(Base, UUIDMixin, MetadataMixin):
    __tablename__ = "channel_memory_gate_traces"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    channel_binding_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("channel_bindings.id"), nullable=False)
    channel_message_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_message_events.id"), nullable=True
    )
    channel_memory_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("channel_memory_candidates.id"), nullable=True
    )
    memory_gate_decision: Mapped[str] = mapped_column(Text, nullable=False)
    memory_gate_status: Mapped[str] = mapped_column(Text, default="recorded")
    gate_summary: Mapped[str] = mapped_column(Text, default="")
    safe_gate_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


__all__ = [
    "ChannelProvider",
    "ChannelProviderConfig",
    "ChannelBotRegistry",
    "ChannelBinding",
    "ChannelWebhookEvent",
    "ChannelDeliveryEvent",
    "ChannelRateLimitEvent",
    "ChannelFailureEvent",
    "ChannelEphemeralBuffer",
    "ChannelEphemeralBufferItem",
    "ChannelMemoryCandidate",
    "ChannelMemoryReview",
    "ChannelContextRedactionEvent",
    "ChannelPresencePolicy",
    "ChannelCheckinSetting",
    "ChannelPresenceBudgetEvent",
    "ChannelQuietHourRule",
    "ChannelFocusModeRule",
    "ChannelMeaningfulSilenceEvent",
    "ChannelOutboundSuppressionEvent",
    "ChannelTraceEvent",
    "ChannelAuditLog",
    "ChannelBindingStatusEvent",
    "ChannelOutboundAuditEvent",
    "ChannelMemoryGateTrace",
]
