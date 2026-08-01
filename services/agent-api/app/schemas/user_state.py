"""Continuity User State Snapshot schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


SignalType = Literal[
    "project_activity", "creative_activity", "interaction_acceptance", "focus_load",
    "presence_acceptance",
    "presence_dismissal", "memory_review_activity",
    "growth_review_activity", "continuity_need",
    "recent_confusion", "recent_satisfaction",
]


class UserStateSnapshotRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    trace_run_id: uuid.UUID | None = None
    signal_type: SignalType
    mode_key: str | None = None
    observed_value: float = Field(default=0.0, ge=0, le=1)
    previous_smoothed_value: float | None = None
    smoothed_value: float = Field(default=0.0, ge=0, le=1)
    smoothing_factor: float = Field(default=0.8, ge=0, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)
    source_event_count: int = 1
    observation_window_start: datetime | None = None
    observation_window_end: datetime | None = None
    reason: str | None = None
    source_feedback_event_ids: list[uuid.UUID] = Field(default_factory=list)
    state_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class UserStateSnapshotListQuery(BaseModel):
    companion_id: uuid.UUID | None = None
    signal_type: SignalType | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class UserStateOverrideRequest(BaseModel):
    user_id: uuid.UUID
    companion_id: uuid.UUID
    signal_type: SignalType
    value: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1, max_length=500)
    mode_key: str | None = None


class UserStateResetRequest(BaseModel):
    user_id: uuid.UUID
    companion_id: uuid.UUID
    signal_type: SignalType
    baseline: float = Field(default=0.5, ge=0, le=1)
    reason: str = Field(min_length=1, max_length=500)
    mode_key: str | None = None
