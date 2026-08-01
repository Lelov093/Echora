"""Continuity Memory Impact schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class ImpactRef(BaseModel):
    type: Literal[
        "response", "memory", "growth_candidate", "growth_record",
        "presence_opportunity", "relationship_explanation",
        "trace_run", "continuity_snapshot",
    ]
    id: uuid.UUID
    title: str | None = None
    summary: str | None = None
    created_at: datetime | None = None


class MemoryImpactOverview(BaseModel):
    memory_id: uuid.UUID
    memory_summary: str | None = None
    memory_type: str | None = None
    memory_state: str | None = None
    memory_strength: float = 0.0
    confidence: float = 0.0
    used_in_responses: int = 0
    used_in_growth: int = 0
    used_in_presence: int = 0
    used_in_relationship: int = 0
    helpful_count: int = 0
    irrelevant_count: int = 0
    outdated_count: int = 0
    wrong_count: int = 0
    feedback_score: float = 0.0
    last_used_at: datetime | None = None
    last_feedback_at: datetime | None = None


class MemoryImpactResponse(BaseModel):
    overview: MemoryImpactOverview
    recent_usage: list[ImpactRef] = Field(default_factory=list)
    growth_impact: list[ImpactRef] = Field(default_factory=list)
    presence_impact: list[ImpactRef] = Field(default_factory=list)
    relationship_impact: list[ImpactRef] = Field(default_factory=list)
    feedback_events: list[ImpactRef] = Field(default_factory=list)
