"""Realtime compatibility multimodal context and permission schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MultimodalContextEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_session_id: uuid.UUID | None = None
    co_presence_session_id: uuid.UUID | None = None
    shared_scene_id: uuid.UUID | None = None
    source_participant_id: uuid.UUID | None = None
    context_type: str
    context_source: str
    context_status: str
    raw_data_ref: str | None = None
    raw_data_retention_policy: str
    raw_data_storage_allowed: bool = False
    retention_policy_json: dict[str, Any] = Field(default_factory=dict)
    permission_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    visibility_summary_json: dict[str, Any] = Field(default_factory=dict)
    redaction_status: str
    expires_at: datetime | None = None
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class ImageContextEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    context_event_id: uuid.UUID
    image_context_kind: str
    image_count: int
    image_ref_json: dict[str, Any] = Field(default_factory=dict)
    image_summary: str | None = None

    model_config = {"from_attributes": True}


class ScreenContextEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    context_event_id: uuid.UUID
    screen_context_kind: str
    window_title: str | None = None
    screen_summary: str | None = None
    capture_ref: str | None = None
    requires_manual_user_action: bool = True

    model_config = {"from_attributes": True}


class FileContextRealtimeEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    context_event_id: uuid.UUID
    file_context_kind: str
    file_document_id: uuid.UUID | None = None
    file_name: str | None = None
    file_mime_type: str | None = None
    file_ref: str | None = None
    excerpt_text: str | None = None
    file_summary: str | None = None

    model_config = {"from_attributes": True}


class DeviceContextEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    context_event_id: uuid.UUID
    device_event_kind: str
    device_label: str | None = None
    event_summary: str | None = None
    requires_manual_user_action: bool = True
    device_payload_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ParticipantContextPermissionRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    context_event_id: uuid.UUID
    realtime_session_id: uuid.UUID | None = None
    participant_id: uuid.UUID
    permission_source: str
    can_see: bool = True
    can_use: bool = True
    can_remember: bool = False
    can_view_raw_data: bool = False
    review_required: bool = True
    expires_at: datetime | None = None
    permission_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    boundary_policy_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ContextRetentionPolicyRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    context_event_id: uuid.UUID | None = None
    realtime_session_id: uuid.UUID | None = None
    policy_scope: str
    retention_policy: str
    redaction_status: str
    raw_data_storage_allowed: bool = False
    expires_at: datetime | None = None
    policy_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class EphemeralContextExpiryEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    context_event_id: uuid.UUID | None = None
    retention_policy_id: uuid.UUID | None = None
    expiry_status: str
    scheduled_for: datetime | None = None
    expired_at: datetime | None = None
    raw_data_deleted: bool = False
    redaction_applied: bool = False
    expiry_payload_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class MultimodalContextEventCreate(BaseModel):
    realtime_session_id: uuid.UUID | None = None
    context_type: str
    context_source: str = "manual_user_action"
    raw_data_retention_policy: str = "ephemeral"
    raw_data_storage_allowed: bool = False
    permission_snapshot_json: dict[str, Any] = Field(default_factory=dict)
