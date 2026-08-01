"""Companion companion memory / shared memory schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CompanionMemoryScopeRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    scope_type: str
    scope_key: str
    title: str
    description: str | None = None
    scope_status: str
    default_write_policy: str
    visibility_policy_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class SharedEpisodicMemoryRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    title: str | None = None
    summary: str
    content: str
    status: str
    source_type: str
    visibility_policy_json: dict[str, Any] = Field(default_factory=dict)
    scene_context_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class SharedMemoryParticipantRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    shared_memory_id: uuid.UUID
    participant_type: str
    participant_user_id: uuid.UUID | None = None
    participant_companion_id: uuid.UUID | None = None
    participant_role: str
    private_memory_sync_policy: str

    model_config = {"from_attributes": True}


class SharedMemoryCandidateRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    source_memory_candidate_id: uuid.UUID | None = None
    source_memory_id: uuid.UUID | None = None
    proposed_shared_memory_id: uuid.UUID | None = None
    source_shared_experience_record_id: uuid.UUID | None = None
    title: str | None = None
    summary: str
    content: str
    candidate_status: str
    requires_user_review: bool = True
    candidate_policy_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class CrossCompanionMemoryEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    source_companion_id: uuid.UUID
    target_companion_id: uuid.UUID
    memory_id: uuid.UUID | None = None
    shared_memory_id: uuid.UUID | None = None
    event_type: str
    status: str
    reason: str | None = None
    review_required: bool = True
    policy_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class CrossCompanionMemoryReviewRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    cross_companion_memory_event_id: uuid.UUID
    decision: str
    review_reason: str | None = None
    approved_policy_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class PrivateToSharedMemoryReviewRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    source_companion_id: uuid.UUID
    memory_id: uuid.UUID
    shared_memory_candidate_id: uuid.UUID | None = None
    target_shared_memory_id: uuid.UUID | None = None
    decision: str
    review_reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SharedToPrivateMemoryReviewRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    target_companion_id: uuid.UUID
    shared_memory_id: uuid.UUID
    target_memory_id: uuid.UUID | None = None
    decision: str
    review_reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SharedEpisodicMemoryCreate(BaseModel):
    title: str | None = None
    summary: str
    content: str
    status: str = "active"
    source_type: str = "candidate_review"
    visibility_policy_json: dict[str, Any] = Field(default_factory=dict)
    scene_context_json: dict[str, Any] = Field(default_factory=dict)
    participants: list[dict[str, Any]] = Field(default_factory=list)


class SharedMemoryCandidateCreate(BaseModel):
    source_memory_candidate_id: uuid.UUID | None = None
    source_memory_id: uuid.UUID | None = None
    source_shared_experience_record_id: uuid.UUID | None = None
    title: str | None = None
    summary: str
    content: str
    requires_user_review: bool = True
    candidate_policy_json: dict[str, Any] = Field(default_factory=dict)


class CrossCompanionMemoryReviewCreate(BaseModel):
    cross_companion_memory_event_id: uuid.UUID
    decision: str = "pending"
    review_reason: str | None = None
    approved_policy_json: dict[str, Any] = Field(default_factory=dict)


class MemoryReviewDecisionRequest(BaseModel):
    decision: str
    review_reason: str | None = None
    approved_policy_json: dict[str, Any] = Field(default_factory=dict)
    target_shared_memory_id: uuid.UUID | None = None
    target_memory_id: uuid.UUID | None = None

