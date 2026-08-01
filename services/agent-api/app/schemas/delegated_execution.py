"""Companion delegated execution support schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DelegatedExecutionIntent(BaseModel):
    task_title: str
    task_summary: str
    requested_by_companion_id: uuid.UUID | None = None
    co_presence_session_id: uuid.UUID | None = None
    shared_scene_id: uuid.UUID | None = None
    tool_constraints: dict[str, Any] = Field(default_factory=dict)
    memory_boundary_json: dict[str, Any] = Field(default_factory=dict)


class DelegatedExecutionResultEnvelope(BaseModel):
    tool_run_id: uuid.UUID | None = None
    trace_run_id: uuid.UUID | None = None
    status: str = "pending"
    result_summary: str | None = None
    acceptance_note: str | None = None
    committed_to_shared_history: bool = False
    completed_at: datetime | None = None


class DelegatedExecutionMemoryContext(BaseModel):
    allowed_private_memory_ids: list[uuid.UUID] = Field(default_factory=list)
    allowed_shared_memory_ids: list[uuid.UUID] = Field(default_factory=list)
    user_global_memory_scope: str = "low_risk_summary_only"
    review_required: bool = True

