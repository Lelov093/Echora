"""Continuity Relationship Explanation schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


RelationshipDimension = Literal[
    "familiarity", "understanding", "collaboration",
    "trust", "emotional_closeness", "boundary_awareness", "continuity",
]


class RelationshipExplanationRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    trace_run_id: uuid.UUID | None = None
    relationship_event_id: uuid.UUID | None = None
    dimension: RelationshipDimension
    previous_value: float | None = None
    new_value: float | None = None
    delta: float | None = None
    title: str | None = None
    explanation: str
    evidence_memory_ids: list[uuid.UUID] = Field(default_factory=list)
    evidence_message_ids: list[uuid.UUID] = Field(default_factory=list)
    evidence_growth_record_ids: list[uuid.UUID] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    user_visible: bool = True
    user_confirmed: bool = False
    score_json: dict[str, Any] = Field(default_factory=dict)
    impact_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class RelationshipExplanationListQuery(BaseModel):
    companion_id: uuid.UUID | None = None
    dimension: RelationshipDimension | None = None
    user_visible: bool | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)
