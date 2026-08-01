"""Agent execution evidence and consistency schemas."""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


EvidenceTargetType = Literal[
    "assistant_response", "memory_candidate", "growth_candidate", "tool_result",
    "file_answer", "evaluation_result", "project_task_suggestion", "presence_opportunity",
]


class EvidenceSufficiencyEventCreate(BaseModel):
    target_type: EvidenceTargetType
    target_id: uuid.UUID | None = None
    sufficiency_score: float = Field(default=0.0, ge=0, le=1)
    status: Literal["sufficient", "needs_more_evidence", "conflicting", "unverified", "not_applicable"] = "needs_more_evidence"
    missing_evidence_json: list[dict[str, Any]] = Field(default_factory=list)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    explanation: str | None = None


class EvidenceSufficiencyEventRead(EvidenceSufficiencyEventCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    trace_run_id: uuid.UUID | None = None

    model_config = {"from_attributes": True}


class GrowthConsistencyCheckRead(BaseModel):
    id: uuid.UUID
    growth_candidate_id: uuid.UUID | None = None
    trace_run_id: uuid.UUID | None = None
    consistency_score: float = Field(default=0.5, ge=0, le=1)
    risk_level: Literal["low", "medium", "high", "critical"] = "medium"
    status: Literal["passed", "warning", "blocked", "needs_review"] = "needs_review"
    conflict_json: dict[str, Any] = Field(default_factory=dict)
    duplication_json: dict[str, Any] = Field(default_factory=dict)
    profile_patch_preview_json: dict[str, Any] = Field(default_factory=dict)
    recommendation: str | None = None

    model_config = {"from_attributes": True}


class OutdatedMemoryFlagCreate(BaseModel):
    memory_id: uuid.UUID
    reason: str
    confidence: float = Field(default=0.5, ge=0, le=1)
    suggested_action: Literal["review", "keep", "edit", "fade", "suppress", "archive", "delete", "reject_flag"] = "review"
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)


class OutdatedMemoryFlagRead(OutdatedMemoryFlagCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    status: Literal["open", "reviewed", "dismissed", "resolved"] = "open"

    model_config = {"from_attributes": True}
