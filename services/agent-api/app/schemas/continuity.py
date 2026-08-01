"""Continuity Continuity Snapshot schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ContinuitySnapshotType = Literal[
    "conversation_end", "manual_refresh", "hub_refresh",
    "agent_run", "scheduled_maintenance", "user_requested",
]


class ContinuitySnapshotRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    trace_run_id: uuid.UUID | None = None
    snapshot_type: ContinuitySnapshotType = "agent_run"
    mode_key: str = "project"
    current_topic: str | None = None
    current_goal: str | None = None
    current_phase: str | None = None
    last_user_intent: str | None = None
    last_assistant_summary: str | None = None
    open_threads: list[dict[str, Any]] = Field(default_factory=list)
    unresolved_decisions: list[dict[str, Any]] = Field(default_factory=list)
    pending_reviews: list[dict[str, Any]] = Field(default_factory=list)
    suggested_next_steps: list[dict[str, Any]] = Field(default_factory=list)
    relevant_memory_ids: list[uuid.UUID] = Field(default_factory=list)
    relevant_growth_record_ids: list[uuid.UUID] = Field(default_factory=list)
    continuity_score: float = Field(default=0.5, ge=0, le=1)
    freshness_score: float = Field(default=0.5, ge=0, le=1)
    user_confirmed: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class ContinuitySnapshotListQuery(BaseModel):
    conversation_id: uuid.UUID | None = None
    snapshot_type: ContinuitySnapshotType | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class RefreshContinuityRequest(BaseModel):
    conversation_id: uuid.UUID | None = None
    mode_key: str = "project"
    snapshot_type: ContinuitySnapshotType = "manual_refresh"


class CorrectContinuityRequest(BaseModel):
    current_topic: str | None = None
    current_goal: str | None = None
    open_threads: list[dict[str, Any]] | None = None
    suggested_next_steps: list[dict[str, Any]] | None = None
    note: str | None = None


class ContinuitySummaryResponse(BaseModel):
    latest_snapshot: ContinuitySnapshotRead | None = None
    conversation_id: uuid.UUID | None = None
    open_thread_count: int = 0
    pending_review_count: int = 0
    unresolved_decision_count: int = 0
    next_step_summary: str | None = None
    continuity_score: float = 0.5
