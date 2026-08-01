"""Realtime compatibility channel gateway readiness schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class PresenceChannelBindingRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID | None = None
    realtime_session_id: uuid.UUID | None = None
    binding_status: str
    channel_kind: str
    connector_kind: str
    external_channel_label: str | None = None
    external_channel_ref_hash: str | None = None
    stores_plaintext_token: bool = False
    credentials_ref: str | None = None
    can_receive_inbound: bool = False
    can_send_outbound: bool = False
    requires_user_approval: bool = True
    readiness_notes: str | None = None
    permission_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    boundary_snapshot_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class CompanionChannelIdentityRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    presence_channel_binding_id: uuid.UUID
    companion_id: uuid.UUID
    identity_status: str
    display_name: str | None = None
    external_identity_ref_hash: str | None = None
    persona_projection_policy: str
    can_present_companion_identity: bool = False
    can_autonomously_message: bool = False
    identity_profile_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ChannelPermissionPolicyRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    presence_channel_binding_id: uuid.UUID
    policy_status: str
    inbound_policy: str
    outbound_policy: str
    inbound_enabled: bool = False
    outbound_enabled: bool = False
    requires_user_approval: bool = True
    allows_memory_read: bool = False
    allows_memory_write: bool = False
    allows_raw_attachment_storage: bool = False
    allows_unsolicited_message: bool = False
    permission_policy_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ChannelMessageEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    presence_channel_binding_id: uuid.UUID
    companion_id: uuid.UUID | None = None
    realtime_session_id: uuid.UUID | None = None
    channel_permission_policy_id: uuid.UUID | None = None
    message_direction: str
    message_status: str
    message_summary: str
    raw_message_ref: str | None = None
    raw_message_storage_allowed: bool = False
    memory_candidate_policy: str
    requires_user_review: bool = True
    redaction_status: str
    message_payload_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelMemoryBoundaryPolicyRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    presence_channel_binding_id: uuid.UUID
    policy_status: str
    memory_read_scope: str
    memory_write_policy: str
    private_memory_access_allowed: bool = False
    shared_memory_write_requires_review: bool = True
    cross_companion_memory_allowed: bool = False
    raw_message_to_memory_allowed: bool = False
    boundary_policy_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ChannelAuditEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    presence_channel_binding_id: uuid.UUID
    channel_message_event_id: uuid.UUID | None = None
    audit_event_type: str
    audit_status: str
    audit_summary: str | None = None
    audit_payload_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class ChannelRevokeEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    presence_channel_binding_id: uuid.UUID
    revoke_status: str
    revoke_scope: str
    revokes_credentials_ref: bool = True
    stops_inbound: bool = True
    stops_outbound: bool = True
    audit_required: bool = True
    revoke_reason: str | None = None
    revoke_payload_json: dict[str, Any] = Field(default_factory=dict)
    applied_at: datetime | None = None

    model_config = {"from_attributes": True}


class PresenceChannelBindingCreate(BaseModel):
    companion_id: uuid.UUID | None = None
    realtime_session_id: uuid.UUID | None = None
    channel_kind: str = "readiness_stub"
    connector_kind: str = "readiness_stub"
    external_channel_label: str | None = None
    credentials_ref: str | None = None
    stores_plaintext_token: bool = False
    requires_user_approval: bool = True
    permission_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    boundary_snapshot_json: dict[str, Any] = Field(default_factory=dict)
