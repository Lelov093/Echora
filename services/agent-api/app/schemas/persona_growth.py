"""Companion persona growth / drift guard schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CompanionPersonaGrowthCandidateRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    source_growth_candidate_id: uuid.UUID | None = None
    shared_experience_record_id: uuid.UUID | None = None
    co_presence_session_id: uuid.UUID | None = None
    source_trace_run_id: uuid.UUID | None = None
    growth_dimension: str
    impact_level: str
    candidate_status: str
    growth_summary: str
    evidence_summary: str | None = None
    proposed_persona_patch_json: dict[str, Any] = Field(default_factory=dict)
    proposed_presence_patch_json: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.5
    evidence_score: float = 0.0
    requires_user_review: bool = True
    review_reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanionPersonaGrowthEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    source_persona_growth_candidate_id: uuid.UUID | None = None
    source_growth_record_id: uuid.UUID | None = None
    source_trace_run_id: uuid.UUID | None = None
    co_presence_session_id: uuid.UUID | None = None
    event_type: str
    impact_level: str
    event_summary: str
    applied_patch_json: dict[str, Any] = Field(default_factory=dict)
    evidence_json: dict[str, Any] = Field(default_factory=dict)
    review_required: bool = True
    occurred_at: datetime

    model_config = {"from_attributes": True}


class CompanionPersonaDriftCheckRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    source_trace_run_id: uuid.UUID | None = None
    source_growth_candidate_id: uuid.UUID | None = None
    source_persona_growth_candidate_id: uuid.UUID | None = None
    co_presence_session_id: uuid.UUID | None = None
    shared_scene_id: uuid.UUID | None = None
    drift_risk_level: str
    check_status: str
    baseline_source: str
    drift_score: float = 0.0
    requires_review: bool = False
    blocks_auto_apply: bool = False
    drift_summary: str | None = None
    evidence_json: dict[str, Any] = Field(default_factory=dict)
    recommendation_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class GroupPersonaConsistencyCheckRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    co_presence_session_id: uuid.UUID | None = None
    shared_scene_id: uuid.UUID | None = None
    source_trace_run_id: uuid.UUID | None = None
    consistency_scope: str
    check_status: str
    consistency_score: float = 0.0
    affected_companion_ids: list[uuid.UUID] = Field(default_factory=list)
    requires_review: bool = False
    consistency_summary: str | None = None
    conflict_json: dict[str, Any] = Field(default_factory=dict)
    recommendation_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanionPersonaGrowthCandidateCreate(BaseModel):
    companion_id: uuid.UUID
    source_growth_candidate_id: uuid.UUID | None = None
    shared_experience_record_id: uuid.UUID | None = None
    co_presence_session_id: uuid.UUID | None = None
    source_trace_run_id: uuid.UUID | None = None
    growth_dimension: str = "persona_summary"
    impact_level: str = "medium"
    candidate_status: str = "pending_review"
    growth_summary: str
    evidence_summary: str | None = None
    proposed_persona_patch_json: dict[str, Any] = Field(default_factory=dict)
    proposed_presence_patch_json: dict[str, Any] = Field(default_factory=dict)
    confidence: float = 0.5
    evidence_score: float = 0.0
    requires_user_review: bool = True
    review_reason: str | None = None


class CompanionPersonaGrowthDecisionRequest(BaseModel):
    candidate_status: str
    review_reason: str | None = None
    proposed_persona_patch_json: dict[str, Any] = Field(default_factory=dict)
    proposed_presence_patch_json: dict[str, Any] = Field(default_factory=dict)

