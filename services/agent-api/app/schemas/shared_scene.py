"""Companion shared scene schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SharedSceneRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    co_presence_session_id: uuid.UUID | None = None
    owner_companion_id: uuid.UUID | None = None
    scene_title: str
    scene_summary: str | None = None
    scene_type: str
    scene_status: str
    source_type: str
    focal_topic: str | None = None
    visibility_scope: str
    context_json: dict[str, Any] = Field(default_factory=dict)
    visibility_policy_json: dict[str, Any] = Field(default_factory=dict)
    opened_at: datetime
    closed_at: datetime | None = None

    model_config = {"from_attributes": True}


class SharedSceneEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    shared_scene_id: uuid.UUID
    co_presence_session_id: uuid.UUID | None = None
    participant_id: uuid.UUID | None = None
    event_type: str
    event_source: str
    title: str
    content: str | None = None
    visibility_scope: str
    triggers_shared_experience_candidate: bool = False
    event_payload_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime

    model_config = {"from_attributes": True}


class SharedExperienceRecordRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    co_presence_session_id: uuid.UUID | None = None
    shared_scene_id: uuid.UUID | None = None
    source_scene_event_id: uuid.UUID | None = None
    source_conversation_id: uuid.UUID | None = None
    source_trace_run_id: uuid.UUID | None = None
    source_type: str
    experience_title: str | None = None
    experience_summary: str
    experience_detail: str | None = None
    experience_status: str
    recommended_memory_action: str
    review_required: bool = True
    created_by_participant_id: uuid.UUID | None = None
    approved_shared_memory_id: uuid.UUID | None = None
    policy_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime

    model_config = {"from_attributes": True}


class SharedSceneCreate(BaseModel):
    co_presence_session_id: uuid.UUID | None = None
    owner_companion_id: uuid.UUID | None = None
    scene_title: str
    scene_summary: str | None = None
    scene_type: str = "conversation"
    scene_status: str = "active"
    source_type: str = "co_presence_session"
    focal_topic: str | None = None
    visibility_scope: str = "role_summary"
    context_json: dict[str, Any] = Field(default_factory=dict)
    visibility_policy_json: dict[str, Any] = Field(default_factory=dict)


class SharedScenePatch(BaseModel):
    scene_title: str | None = None
    scene_summary: str | None = None
    scene_status: str | None = None
    focal_topic: str | None = None
    visibility_scope: str | None = None
    context_json: dict[str, Any] | None = None
    visibility_policy_json: dict[str, Any] | None = None
    closed_at: datetime | None = None


class SharedSceneEventCreate(BaseModel):
    co_presence_session_id: uuid.UUID | None = None
    participant_id: uuid.UUID | None = None
    event_type: str = "scene_note"
    event_source: str = "system"
    title: str = ""
    content: str | None = None
    visibility_scope: str = "role_summary"
    triggers_shared_experience_candidate: bool = False
    event_payload_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class SharedExperienceRecordCreate(BaseModel):
    co_presence_session_id: uuid.UUID | None = None
    shared_scene_id: uuid.UUID | None = None
    source_scene_event_id: uuid.UUID | None = None
    source_conversation_id: uuid.UUID | None = None
    source_trace_run_id: uuid.UUID | None = None
    source_type: str = "session"
    experience_title: str | None = None
    experience_summary: str
    experience_detail: str | None = None
    experience_status: str = "captured"
    recommended_memory_action: str = "shared_candidate"
    review_required: bool = True
    created_by_participant_id: uuid.UUID | None = None
    approved_shared_memory_id: uuid.UUID | None = None
    policy_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

