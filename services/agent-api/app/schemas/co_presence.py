"""Companion co-presence schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CoPresenceSessionRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    primary_companion_id: uuid.UUID
    originating_conversation_id: uuid.UUID | None = None
    session_title: str
    session_summary: str | None = None
    session_status: str
    session_source: str
    visibility_scope: str
    entry_reason: str | None = None
    participant_summary_json: dict[str, Any] = Field(default_factory=dict)
    boundary_summary_json: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime
    ended_at: datetime | None = None

    model_config = {"from_attributes": True}


class CoPresenceParticipantRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    co_presence_session_id: uuid.UUID
    participant_type: str
    participant_role: str
    participant_user_id: uuid.UUID | None = None
    participant_companion_id: uuid.UUID | None = None
    external_agent_label: str | None = None
    join_status: str
    visibility_scope: str
    can_speak: bool = True
    can_delegate: bool = False
    joined_at: datetime
    left_at: datetime | None = None
    policy_override_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class CoPresenceSessionPolicyRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    co_presence_session_id: uuid.UUID
    policy_status: str
    default_primary_memory_participation: str
    default_active_memory_participation: str
    default_observing_memory_participation: str
    default_delegated_memory_participation: str
    user_global_memory_scope: str
    cross_companion_private_read_policy: str
    private_to_shared_policy: str
    shared_to_private_policy: str
    allow_observing_companion_long_term_memory: bool = False
    allow_autonomous_companion_interaction: bool = False
    session_visibility_policy_json: dict[str, Any] = Field(default_factory=dict)
    boundary_policy_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ParticipantAwarenessStateRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    co_presence_session_id: uuid.UUID
    participant_id: uuid.UUID
    target_participant_id: uuid.UUID | None = None
    awareness_type: str
    awareness_level: str
    awareness_status: str
    updated_by_source: str
    awareness_summary: str | None = None
    awareness_json: dict[str, Any] = Field(default_factory=dict)
    updated_at: datetime

    model_config = {"from_attributes": True}


class ParticipantMemoryPermissionRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    co_presence_session_id: uuid.UUID
    participant_id: uuid.UUID
    permission_source: str
    memory_participation_override: str | None = None
    allow_private_candidate: bool | None = None
    allow_shared_candidate: bool | None = None
    allow_user_global_summary_read: bool | None = None
    allow_user_global_full_read: bool | None = None
    allow_cross_companion_private_read: bool | None = None
    allow_private_to_shared_sync: bool | None = None
    allow_shared_to_private_sync: bool | None = None
    review_required: bool = True
    boundary_policy_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class CoPresenceSessionCreate(BaseModel):
    primary_companion_id: uuid.UUID
    originating_conversation_id: uuid.UUID | None = None
    session_title: str = ""
    session_summary: str | None = None
    session_source: str = "direct_conversation"
    visibility_scope: str = "role_summary"
    entry_reason: str | None = None


class CoPresenceSessionPatch(BaseModel):
    session_title: str | None = None
    session_summary: str | None = None
    session_status: str | None = None
    visibility_scope: str | None = None
    ended_at: datetime | None = None


class CoPresenceParticipantCreate(BaseModel):
    participant_type: str
    participant_role: str
    participant_user_id: uuid.UUID | None = None
    participant_companion_id: uuid.UUID | None = None
    external_agent_label: str | None = None
    visibility_scope: str = "role_summary"
    can_speak: bool = True
    can_delegate: bool = False
    policy_override_json: dict[str, Any] = Field(default_factory=dict)


class CoPresenceParticipantPatch(BaseModel):
    participant_role: str | None = None
    join_status: str | None = None
    visibility_scope: str | None = None
    can_speak: bool | None = None
    can_delegate: bool | None = None
    left_at: datetime | None = None
    policy_override_json: dict[str, Any] | None = None


class ParticipantAwarenessStateUpsert(BaseModel):
    target_participant_id: uuid.UUID | None = None
    awareness_type: str = "participant_presence"
    awareness_level: str = "full"
    awareness_status: str = "active"
    updated_by_source: str = "system"
    awareness_summary: str | None = None
    awareness_json: dict[str, Any] = Field(default_factory=dict)


class ParticipantMemoryPermissionUpsert(BaseModel):
    permission_source: str = "session_default"
    memory_participation_override: str | None = None
    allow_private_candidate: bool | None = None
    allow_shared_candidate: bool | None = None
    allow_user_global_summary_read: bool | None = None
    allow_user_global_full_read: bool | None = None
    allow_cross_companion_private_read: bool | None = None
    allow_private_to_shared_sync: bool | None = None
    allow_shared_to_private_sync: bool | None = None
    review_required: bool = True
    boundary_policy_json: dict[str, Any] = Field(default_factory=dict)

