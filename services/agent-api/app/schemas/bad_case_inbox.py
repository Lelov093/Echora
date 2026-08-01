"""Agent execution bad case inbox schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


BadCaseInboxStatus = Literal["new", "triaged", "linked", "converted", "dismissed", "resolved"]


class BadCaseInboxItemCreate(BaseModel):
    source_type: str
    case_type: str
    title: str
    description: str | None = None
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    trace_run_id: uuid.UUID | None = None
    replay_id: uuid.UUID | None = None
    feedback_event_id: uuid.UUID | None = None
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)


class BadCaseInboxItemRead(BadCaseInboxItemCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    status: BadCaseInboxStatus = "new"
    created_bad_case_id: uuid.UUID | None = None
    created_regression_case_id: uuid.UUID | None = None
    assigned_to: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class BadCaseTriageRequest(BaseModel):
    new_status: BadCaseInboxStatus
    action: str
    note: str | None = None
