"""Agent execution replay schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ReplayStatus = Literal["created", "running", "completed", "failed", "cancelled"]


class AgentRunReplayCreate(BaseModel):
    trace_run_id: uuid.UUID | None = None
    replay_type: Literal["static", "rerun", "what_if"] = "static"
    input_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    trace_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    output_snapshot_json: dict[str, Any] = Field(default_factory=dict)


class AgentRunReplayRead(AgentRunReplayCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    status: ReplayStatus = "created"
    diff_json: dict[str, Any] = Field(default_factory=dict)
    replayed_at: datetime | None = None
    score: float | None = Field(default=None, ge=0, le=1)

    model_config = {"from_attributes": True}


class ReplayAnnotationCreate(BaseModel):
    annotation_type: str
    target_ref_json: dict[str, Any] = Field(default_factory=dict)
    content: str
    severity: str | None = None
