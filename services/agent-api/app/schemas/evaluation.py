"""Agent execution evaluation schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


EvaluationStatus = Literal["draft", "active", "archived"]
RunStatus = Literal["created", "running", "completed", "failed", "cancelled"]
ResultStatus = Literal["pending", "passed", "failed", "skipped", "error"]


class EvaluationDatasetCreate(BaseModel):
    name: str
    description: str | None = None
    dataset_type: str = "manual"
    status: EvaluationStatus = "draft"


class EvaluationDatasetRead(EvaluationDatasetCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class EvaluationCaseCreate(BaseModel):
    dataset_id: uuid.UUID
    case_type: str
    title: str
    input_json: dict[str, Any] = Field(default_factory=dict)
    expected_behavior: str | None = None
    expected_json: dict[str, Any] = Field(default_factory=dict)


class EvaluationRunRead(BaseModel):
    id: uuid.UUID
    dataset_id: uuid.UUID | None = None
    status: RunStatus = "created"
    judge_type: Literal["manual", "rule_based", "simulation_judge", "llm_judge"] = "manual"
    aggregate_score: float | None = Field(default=None, ge=0, le=1)
    total_count: int = 0
    passed_count: int = 0
    failed_count: int = 0

    model_config = {"from_attributes": True}


class EvaluationResultRead(BaseModel):
    id: uuid.UUID
    evaluation_run_id: uuid.UUID
    evaluation_case_id: uuid.UUID | None = None
    status: ResultStatus = "pending"
    score: float | None = Field(default=None, ge=0, le=1)
    output_json: dict[str, Any] = Field(default_factory=dict)
    judge_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}
