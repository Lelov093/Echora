"""Agent execution project schemas."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


MilestoneStatus = Literal["planned", "active", "completed", "blocked", "cancelled", "archived"]
TaskStatus = Literal["todo", "in_progress", "blocked", "done", "cancelled", "archived"]
EvidenceType = Literal[
    "trace", "trace_run", "trace_step", "memory", "file", "file_document",
    "file_chunk", "tool", "tool_run", "bad_case", "regression_case",
    "evaluation_result",
]


class ProjectMilestoneCreate(BaseModel):
    title: str
    description: str | None = None
    status: MilestoneStatus = "planned"
    target_at: datetime | None = None
    priority: float = Field(default=0.5, ge=0, le=1)


class ProjectMilestoneRead(ProjectMilestoneCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    completed_at: datetime | None = None

    model_config = {"from_attributes": True}


class ProjectTaskCreate(BaseModel):
    title: str
    description: str | None = None
    milestone_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    status: TaskStatus = "todo"
    priority: float = Field(default=0.5, ge=0, le=1)
    due_at: datetime | None = None


class ProjectTaskRead(ProjectTaskCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    completed_at: datetime | None = None
    evidence_summary: str | None = None

    model_config = {"from_attributes": True}


class ProjectTaskEvidenceLinkCreate(BaseModel):
    evidence_type: EvidenceType
    evidence_id: uuid.UUID | None = None
    evidence_uri: str | None = None
    relevance_score: float = Field(default=0.5, ge=0, le=1)
    note: str | None = None
