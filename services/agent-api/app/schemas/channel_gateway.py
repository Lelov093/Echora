"""Channel Gateway Companion Channel Gateway schemas.

Read schemas intentionally do not expose token_secret_ref. Secret references are
write-only inputs and must be resolved server-side by dedicated services.
"""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ChannelProviderRead(BaseModel):
    id: uuid.UUID
    provider_key: str
    provider_display_name: str
    provider_kind: str
    provider_status: str
    is_real_provider: bool = False
    supports_multi_bot: bool = False
    supports_inbound: bool = False
    supports_outbound: bool = False
    supports_low_frequency_checkin: bool = False
    requires_external_token: bool = False
    config_schema_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ChannelBotRegistryCreate(BaseModel):
    provider_id: uuid.UUID
    bot_key: str
    bot_display_name: str
    token_secret_ref: str | None = None
    external_application_id_hash: str | None = None
    external_bot_user_id_hash: str | None = None
    safe_metadata_json: dict[str, Any] = Field(default_factory=dict)


class ChannelBotRegistryRead(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    user_id: uuid.UUID | None = None
    bot_key: str
    bot_display_name: str
    bot_status: str
    token_status: str
    stores_plaintext_token: bool = False
    external_application_id_hash: str | None = None
    external_bot_user_id_hash: str | None = None
    safe_metadata_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ChannelProviderConfigRead(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    user_id: uuid.UUID | None = None
    config_status: str
    secret_policy: str
    stores_plaintext_token: bool = False
    safe_public_config_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ChannelBindingCreate(BaseModel):
    companion_id: uuid.UUID
    provider_id: uuid.UUID
    provider_bot_id: uuid.UUID | None = None
    binding_scope: str = "dm"
    permission_scope: str = "reply_only"
    outbound_policy: str = "reply_only"
    memory_policy: str = "ephemeral_review_gated"
    external_channel_ref_hash: str | None = None
    permission_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    boundary_snapshot_json: dict[str, Any] = Field(default_factory=dict)


class ChannelBindingRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    provider_id: uuid.UUID
    provider_bot_id: uuid.UUID | None = None
    presence_channel_binding_id: uuid.UUID | None = None
    binding_status: str
    binding_scope: str
    permission_scope: str
    outbound_policy: str
    memory_policy: str
    requires_user_approval: bool = True
    can_receive_inbound: bool = False
    can_send_outbound: bool = False
    checkin_enabled: bool = False
    memory_write_requires_review: bool = True
    raw_message_storage_allowed: bool = False
    stores_plaintext_token: bool = False
    external_channel_ref_hash: str | None = None
    permission_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    boundary_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    revoked_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelMessageEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    channel_binding_id: uuid.UUID | None = None
    provider_id: uuid.UUID | None = None
    provider_bot_id: uuid.UUID | None = None
    companion_id: uuid.UUID | None = None
    message_direction: str
    message_status: str
    message_summary: str
    external_message_ref_hash: str | None = None
    payload_is_ephemeral: bool = True
    raw_payload_storage_allowed: bool = False
    safe_payload_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelDeliveryEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    channel_binding_id: uuid.UUID
    channel_message_event_id: uuid.UUID | None = None
    provider_id: uuid.UUID
    provider_bot_id: uuid.UUID | None = None
    delivery_status: str
    delivery_mode: str
    delivery_attempt: int = 1
    delivery_summary: str = ""
    raw_payload_storage_allowed: bool = False
    safe_delivery_payload_json: dict[str, Any] = Field(default_factory=dict)
    queued_at: datetime | None = None
    delivered_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelWebhookEventRead(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    provider_bot_id: uuid.UUID | None = None
    channel_binding_id: uuid.UUID | None = None
    channel_message_event_id: uuid.UUID | None = None
    webhook_event_type: str
    webhook_status: str
    payload_summary: str = ""
    raw_payload_storage_allowed: bool = False
    safe_payload_json: dict[str, Any] = Field(default_factory=dict)
    received_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelFailureEventRead(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    provider_bot_id: uuid.UUID | None = None
    channel_binding_id: uuid.UUID | None = None
    failure_type: str
    failure_status: str
    safe_error_summary: str = ""
    safe_error_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelRateLimitEventRead(BaseModel):
    id: uuid.UUID
    provider_id: uuid.UUID
    provider_bot_id: uuid.UUID | None = None
    channel_binding_id: uuid.UUID | None = None
    rate_limit_status: str
    retry_after_seconds: int | None = None
    safe_rate_limit_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelEphemeralBufferRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    channel_binding_id: uuid.UUID
    provider_id: uuid.UUID
    provider_bot_id: uuid.UUID | None = None
    buffer_status: str
    retention_seconds: int
    raw_payload_storage_allowed: bool = False
    memory_candidate_generation_enabled: bool = True
    safe_buffer_summary: str = ""
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelEphemeralBufferItemRead(BaseModel):
    id: uuid.UUID
    channel_ephemeral_buffer_id: uuid.UUID
    channel_message_event_id: uuid.UUID | None = None
    buffer_item_status: str
    safe_content_summary: str = ""
    salience_score: float = 0
    raw_payload_storage_allowed: bool = False
    long_term_memory_written: bool = False
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelMemoryCandidateRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    channel_binding_id: uuid.UUID
    provider_id: uuid.UUID
    provider_bot_id: uuid.UUID | None = None
    candidate_status: str
    target_memory_scope: str
    candidate_summary: str
    suggested_memory_content: str = ""
    salience_score: float = 0
    requires_user_review: bool = True
    auto_commit_allowed: bool = False
    raw_payload_storage_allowed: bool = False
    safe_evidence_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ChannelMemoryReviewRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    channel_memory_candidate_id: uuid.UUID
    review_decision: str
    target_memory_id: uuid.UUID | None = None
    review_notes: str | None = None
    memory_write_allowed_after_review: bool = False
    safe_review_payload_json: dict[str, Any] = Field(default_factory=dict)
    reviewed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelPresencePolicyRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    channel_binding_id: uuid.UUID
    provider_id: uuid.UUID
    provider_bot_id: uuid.UUID | None = None
    policy_status: str
    presence_mode: str
    reply_only_default: bool = True
    low_frequency_checkin_enabled: bool = False
    channel_mute: bool = False
    outbound_disabled: bool = False
    daily_presence_budget: int = 0
    remaining_presence_budget: int = 0
    quiet_hours_enforced: bool = True
    focus_mode_enforced: bool = True
    meaningful_silence_enforced: bool = True
    policy_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ChannelCheckinSettingRead(BaseModel):
    id: uuid.UUID
    channel_presence_policy_id: uuid.UUID
    enabled: bool = False
    frequency: str
    min_interval_seconds: int
    requires_user_opt_in: bool = True
    quiet_hours_enforced: bool = True
    focus_mode_enforced: bool = True
    presence_budget_enforced: bool = True
    meaningful_silence_enforced: bool = True
    next_eligible_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelPresenceBudgetEventRead(BaseModel):
    id: uuid.UUID
    channel_presence_policy_id: uuid.UUID
    event_type: str
    budget_delta: int = 0
    remaining_budget: int = 0
    event_summary: str = ""
    event_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelQuietHourRuleRead(BaseModel):
    id: uuid.UUID
    channel_presence_policy_id: uuid.UUID
    enabled: bool = True
    timezone: str
    start_minute_of_day: int
    end_minute_of_day: int
    applies_to_checkins: bool = True
    applies_to_outbound: bool = True

    model_config = {"from_attributes": True}


class ChannelFocusModeRuleRead(BaseModel):
    id: uuid.UUID
    channel_presence_policy_id: uuid.UUID
    focus_status: str
    suppresses_outbound: bool = True
    suppresses_checkins: bool = True
    focus_reason: str | None = None

    model_config = {"from_attributes": True}


class ChannelMeaningfulSilenceEventRead(BaseModel):
    id: uuid.UUID
    channel_presence_policy_id: uuid.UUID
    silence_reason: str
    suppressed_outbound_count: int = 0
    silence_summary: str = ""
    event_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelOutboundSuppressionEventRead(BaseModel):
    id: uuid.UUID
    channel_presence_policy_id: uuid.UUID
    channel_delivery_event_id: uuid.UUID | None = None
    suppression_reason: str
    suppression_status: str
    suppression_summary: str = ""
    safe_suppression_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelContextRedactionEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    channel_binding_id: uuid.UUID | None = None
    channel_message_event_id: uuid.UUID | None = None
    channel_ephemeral_buffer_item_id: uuid.UUID | None = None
    channel_memory_candidate_id: uuid.UUID | None = None
    redaction_scope: str
    redaction_status: str
    redaction_reason: str | None = None
    safe_redaction_payload_json: dict[str, Any] = Field(default_factory=dict)
    applied_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelAuditLogRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    channel_binding_id: uuid.UUID | None = None
    provider_id: uuid.UUID | None = None
    provider_bot_id: uuid.UUID | None = None
    audit_log_type: str
    audit_summary: str = ""
    safe_audit_payload_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelTraceEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID | None = None
    channel_binding_id: uuid.UUID | None = None
    provider_id: uuid.UUID | None = None
    provider_bot_id: uuid.UUID | None = None
    trace_event_type: str
    trace_status: str
    trace_summary: str = ""
    safe_trace_payload_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelRevokeEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    channel_binding_id: uuid.UUID | None = None
    provider_id: uuid.UUID | None = None
    provider_bot_id: uuid.UUID | None = None
    revoke_status: str
    revoke_scope: str
    stops_inbound: bool = True
    stops_outbound: bool = True
    stops_checkins: bool = True
    clears_ephemeral_buffer: bool = True
    disables_memory_candidates: bool = True
    audit_required: bool = True
    revoke_reason: str | None = None
    applied_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelBindingStatusEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    channel_binding_id: uuid.UUID
    status_event: str
    from_status: str | None = None
    to_status: str
    status_reason: str | None = None
    safe_status_payload_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelOutboundAuditEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    channel_binding_id: uuid.UUID
    channel_delivery_event_id: uuid.UUID | None = None
    channel_message_event_id: uuid.UUID | None = None
    provider_bot_id: uuid.UUID | None = None
    outbound_audit_status: str
    outbound_policy_snapshot: str
    audit_summary: str = ""
    safe_outbound_audit_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelMemoryGateTraceRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    channel_binding_id: uuid.UUID
    channel_message_event_id: uuid.UUID | None = None
    channel_memory_candidate_id: uuid.UUID | None = None
    memory_gate_decision: str
    memory_gate_status: str
    gate_summary: str = ""
    safe_gate_payload_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}
