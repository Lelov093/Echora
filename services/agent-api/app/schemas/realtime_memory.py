"""Realtime compatibility realtime memory buffer schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RealtimeMemoryBufferRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_session_id: uuid.UUID | None = None
    co_presence_session_id: uuid.UUID | None = None
    shared_scene_id: uuid.UUID | None = None
    owner_companion_id: uuid.UUID | None = None
    buffer_scope: str
    buffer_status: str
    default_memory_action: str
    retention_policy: str
    review_required: bool = True
    auto_write_private_memory: bool = False
    auto_write_shared_memory: bool = False
    buffer_summary: str | None = None
    policy_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}


class RealtimeMemoryBufferItemRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    buffer_id: uuid.UUID
    realtime_session_id: uuid.UUID | None = None
    source_type: str
    source_voice_turn_id: uuid.UUID | None = None
    source_context_event_id: uuid.UUID | None = None
    source_session_event_id: uuid.UUID | None = None
    source_channel_event_id: uuid.UUID | None = None
    item_status: str
    retention_policy: str
    content_summary: str | None = None
    raw_content_ref: str | None = None
    can_generate_salient_moment: bool = True
    can_write_long_term_memory: bool = False
    payload_json: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}


class CompanionPrivateRealtimeBufferRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    buffer_id: uuid.UUID
    companion_id: uuid.UUID
    private_memory_sync_policy: str
    auto_write_private_memory: bool = False
    review_required: bool = True
    policy_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class CoPresenceSessionBufferRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    buffer_id: uuid.UUID
    co_presence_session_id: uuid.UUID
    shared_candidate_policy: str
    review_required: bool = True
    policy_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class SharedSceneBufferRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    buffer_id: uuid.UUID
    shared_scene_id: uuid.UUID
    shared_candidate_policy: str
    review_required: bool = True
    policy_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class SalientMomentRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_session_id: uuid.UUID | None = None
    buffer_id: uuid.UUID | None = None
    buffer_item_id: uuid.UUID | None = None
    moment_scope: str
    moment_status: str
    moment_title: str | None = None
    moment_summary: str
    salience_score: float
    review_required: bool = True
    auto_write_disabled: bool = True
    evidence_json: dict[str, Any] = Field(default_factory=dict)
    policy_snapshot_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class CompanionPrivateSalientMomentRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    salient_moment_id: uuid.UUID
    companion_id: uuid.UUID
    private_memory_sync_policy: str
    approved_private_memory_id: uuid.UUID | None = None
    auto_write_private_memory: bool = False
    review_required: bool = True

    model_config = {"from_attributes": True}


class SharedSalientMomentRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    salient_moment_id: uuid.UUID
    shared_scene_id: uuid.UUID | None = None
    proposed_shared_memory_candidate_id: uuid.UUID | None = None
    shared_memory_sync_policy: str
    auto_write_shared_memory: bool = False
    review_required: bool = True

    model_config = {"from_attributes": True}


class RealtimeSharedMemoryCandidateRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_session_id: uuid.UUID | None = None
    salient_moment_id: uuid.UUID | None = None
    source_buffer_id: uuid.UUID | None = None
    source_buffer_item_id: uuid.UUID | None = None
    proposed_shared_memory_candidate_id: uuid.UUID | None = None
    candidate_status: str
    candidate_summary: str | None = None
    requires_user_review: bool = True
    auto_commit_shared_memory: bool = False
    shared_to_private_policy: str
    private_to_shared_policy: str
    candidate_payload_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class RealtimeMemoryExpiryEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    buffer_id: uuid.UUID | None = None
    buffer_item_id: uuid.UUID | None = None
    salient_moment_id: uuid.UUID | None = None
    expiry_status: str
    scheduled_for: datetime | None = None
    expired_at: datetime | None = None
    raw_data_deleted: bool = False
    expiry_payload_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class RealtimeMemoryBufferCreate(BaseModel):
    realtime_session_id: uuid.UUID | None = None
    co_presence_session_id: uuid.UUID | None = None
    shared_scene_id: uuid.UUID | None = None
    owner_companion_id: uuid.UUID | None = None
    buffer_scope: str = "co_presence_session"
    default_memory_action: str = "candidate_review"
    retention_policy: str = "ephemeral"
    review_required: bool = True
