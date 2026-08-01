"""Continuity Memory Abstraction Candidate schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


AbstractionType = Literal[
    "stable_preference", "user_principle", "long_term_goal",
    "companion_strategy", "communication_style", "project_pattern",
    "creative_pattern", "boundary_rule", "self_narrative",
]

AbstractionStatus = Literal[
    "candidate", "accepted", "edited", "rejected", "merged",
    "expired", "committed_to_memory", "committed_to_growth",
]


class MemoryAbstractionCandidateRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    trace_run_id: uuid.UUID | None = None
    source_memory_ids: list[uuid.UUID] = Field(default_factory=list)
    abstraction_type: AbstractionType
    title: str | None = None
    content: str
    summary: str | None = None
    suggested_memory_type: str | None = None
    suggested_growth_type: str | None = None
    evidence_score: float = Field(default=0.0, ge=0, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)
    recurrence: float = Field(default=0.0, ge=0, le=1)
    consistency_score: float = Field(default=0.0, ge=0, le=1)
    risk_score: float = Field(default=0.0, ge=0, le=1)
    reason: str | None = None
    impact_preview: dict[str, Any] = Field(default_factory=dict)
    status: AbstractionStatus = "candidate"
    accepted_memory_id: uuid.UUID | None = None
    accepted_growth_record_id: uuid.UUID | None = None
    edited_content: str | None = None
    rejection_reason: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoryAbstractionCandidateListQuery(BaseModel):
    companion_id: uuid.UUID | None = None
    abstraction_type: AbstractionType | None = None
    status: AbstractionStatus | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class AcceptAbstractionAsMemoryRequest(BaseModel):
    edited_content: str | None = None
    suggested_memory_type: str | None = None
    suggested_half_life_days: float | None = None
    note: str | None = None


class AcceptAbstractionAsGrowthRequest(BaseModel):
    edited_content: str | None = None
    note: str | None = None


class EditAcceptAbstractionRequest(BaseModel):
    edited_content: str
    note: str | None = None


class RejectAbstractionRequest(BaseModel):
    rejection_reason: str | None = None
    note: str | None = None
