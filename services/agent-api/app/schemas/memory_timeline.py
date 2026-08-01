"""Continuity Memory Timeline schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MemoryTimelineItem(BaseModel):
    event_type: str
    event_id: uuid.UUID
    memory_id: uuid.UUID
    memory_summary: str | None = None
    title: str | None = None
    reason: str | None = None
    previous_state: str | None = None
    new_state: str | None = None
    previous_strength: float | None = None
    new_strength: float | None = None
    strength_delta: float | None = None
    previous_confidence: float | None = None
    new_confidence: float | None = None
    confidence_delta: float | None = None
    conversation_id: uuid.UUID | None = None
    trace_run_id: uuid.UUID | None = None
    feedback_event_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoryTimelineResponse(BaseModel):
    memory_id: uuid.UUID
    items: list[MemoryTimelineItem] = Field(default_factory=list)
    total: int = 0


class MemoryUsageEventRead(BaseModel):
    id: uuid.UUID
    memory_id: uuid.UUID
    event_type: str
    semantic_similarity: float | None = None
    retrieval_score: float | None = None
    memory_strength_snapshot: float | None = None
    confidence_snapshot: float | None = None
    rank_before_rerank: int | None = None
    rank_after_rerank: int | None = None
    selected_for_context: bool = False
    used_in_response: bool = False
    used_in_growth: bool = False
    used_in_presence: bool = False
    used_in_relationship: bool = False
    why_selected: str | None = None
    feedback_label: str | None = None
    conversation_id: uuid.UUID | None = None
    trace_run_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoryUsageEventListQuery(BaseModel):
    memory_id: uuid.UUID | None = None
    event_type: str | None = None
    trace_run_id: uuid.UUID | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class MemoryLifecycleEventRead(BaseModel):
    id: uuid.UUID
    memory_id: uuid.UUID
    event_type: str
    title: str | None = None
    reason: str | None = None
    previous_state: str | None = None
    new_state: str | None = None
    previous_strength: float | None = None
    new_strength: float | None = None
    strength_delta: float | None = None
    previous_confidence: float | None = None
    new_confidence: float | None = None
    confidence_delta: float | None = None
    previous_half_life_days: float | None = None
    new_half_life_days: float | None = None
    source_candidate_id: uuid.UUID | None = None
    feedback_event_id: uuid.UUID | None = None
    trace_run_id: uuid.UUID | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class MemoryLifecycleEventListQuery(BaseModel):
    memory_id: uuid.UUID | None = None
    event_type: str | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
