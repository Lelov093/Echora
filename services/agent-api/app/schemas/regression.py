"""Agent execution regression schemas."""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


class RegressionCaseCreate(BaseModel):
    title: str
    expected_behavior: str
    input_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    expected_json: dict[str, Any] = Field(default_factory=dict)
    source_bad_case_id: uuid.UUID | None = None
    source_replay_id: uuid.UUID | None = None
    status: Literal["active", "disabled", "archived"] = "active"


class RegressionCaseRead(RegressionCaseCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID

    model_config = {"from_attributes": True}


class RegressionRunRead(BaseModel):
    id: uuid.UUID
    status: Literal["created", "running", "completed", "failed", "cancelled"] = "created"
    total_count: int = 0
    passed_count: int = 0
    failed_count: int = 0
    summary_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}
