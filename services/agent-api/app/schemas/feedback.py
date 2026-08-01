"""Feedback event API schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


FeedbackTargetType = Literal[
    "memory", "memory_candidate", "growth_candidate", "growth_record",
    "presence_opportunity", "related_memory", "assistant_response",
    "retrieval_result", "trace_run", "conversation", "continuity",
    "relationship", "settings", "strategy",
]

FeedbackAction = Literal[
    "accept", "edit_accept", "reject", "delete", "lock", "fade",
    "archive", "reactivate", "helpful", "irrelevant", "outdated",
    "wrong", "confirm", "revert", "snooze", "dismiss",
    "suppress_type", "accept_presence", "mark_important", "mark_sensitive",
    "shown", "continued", "ignored", "disabled",
    "useful", "too_tool_like", "too_verbose", "too_intrusive",
]

FeedbackLabel = Literal[
    "positive", "weak_positive", "neutral", "weak_negative", "negative", "strong_negative",
]
CalibrationStatus = Literal["pending", "applied", "ignored", "failed"]
FeedbackSource = Literal["explicit", "inferred"]
FeedbackRiskLevel = Literal["low", "medium", "high", "critical"]
RedactionStatus = Literal["not_required", "redacted", "blocked"]


class FeedbackEventCreate(BaseModel):
    target_type: FeedbackTargetType
    target_id: uuid.UUID | None = None
    action: FeedbackAction
    label: FeedbackLabel | None = None
    idempotency_key: str | None = Field(default=None, max_length=200)
    feedback_source: FeedbackSource | None = None
    reward: float | None = Field(default=None, ge=-1, le=1)
    reason: str | None = None
    user_note: str | None = None
    conversation_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    trace_run_id: uuid.UUID | None = None
    score_delta: float = Field(default=0.0, ge=-1, le=1)
    confidence_delta: float = Field(default=0.0, ge=-1, le=1)
    strength_delta: float = Field(default=0.0, ge=-1, le=1)
    priority_delta: float = Field(default=0.0, ge=-1, le=1)
    applies_to_memory: bool = False
    applies_to_growth: bool = False
    applies_to_presence: bool = False
    applies_to_retrieval: bool = False
    applies_to_relationship: bool = False
    applies_to_boundary: bool = False
    context_json: dict[str, Any] = Field(default_factory=dict)
    sample_provenance: dict[str, Any] = Field(default_factory=dict)
    algorithm_key: str | None = None
    algorithm_version: str = "core-feedback-v1"
    risk_level: FeedbackRiskLevel = "low"
    redaction_status: RedactionStatus | None = None
    training_eligible: bool | None = None


class FeedbackEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    message_id: uuid.UUID | None = None
    trace_run_id: uuid.UUID | None = None
    target_type: FeedbackTargetType
    target_id: uuid.UUID | None = None
    action: FeedbackAction
    label: FeedbackLabel
    idempotency_key: str | None = None
    feedback_source: FeedbackSource = "explicit"
    reward: float = 0.0
    reason: str | None = None
    user_note: str | None = None
    score_delta: float = 0.0
    confidence_delta: float = 0.0
    strength_delta: float = 0.0
    priority_delta: float = 0.0
    applies_to_memory: bool = False
    applies_to_growth: bool = False
    applies_to_presence: bool = False
    applies_to_retrieval: bool = False
    applies_to_relationship: bool = False
    applies_to_boundary: bool = False
    calibration_status: CalibrationStatus = "pending"
    applied_at: datetime | None = None
    context_json: dict[str, Any] = Field(default_factory=dict)
    sample_provenance: dict[str, Any] = Field(default_factory=dict)
    context_hash: str | None = None
    algorithm_key: str | None = None
    algorithm_version: str = "core-feedback-v1"
    risk_level: FeedbackRiskLevel = "low"
    redaction_status: RedactionStatus = "not_required"
    training_eligible: bool = True
    idempotent_replay: bool = False
    before_json: dict[str, Any] = Field(default_factory=dict)
    after_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class FeedbackEventUpdate(BaseModel):
    calibration_status: CalibrationStatus | None = None
    reason: str | None = None
    user_note: str | None = None


class FeedbackEventListQuery(BaseModel):
    companion_id: uuid.UUID | None = None
    target_type: FeedbackTargetType | None = None
    target_id: uuid.UUID | None = None
    label: FeedbackLabel | None = None
    calibration_status: CalibrationStatus | None = None
    feedback_source: FeedbackSource | None = None
    risk_level: FeedbackRiskLevel | None = None
    training_eligible: bool | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ApplyFeedbackRequest(BaseModel):
    apply_to_memory: bool = True
    apply_to_growth: bool = True
    apply_to_presence: bool = True
    apply_to_retrieval: bool = True
    note: str | None = None


class ApplyFeedbackResponse(BaseModel):
    feedback_event_id: uuid.UUID
    calibration_status: CalibrationStatus
    effects: list["FeedbackEffect"] = Field(default_factory=list)
    user_visible_summary: str | None = None


class FeedbackEffect(BaseModel):
    target_type: FeedbackTargetType
    target_id: uuid.UUID | None = None
    field_changes: list[dict[str, Any]] = Field(default_factory=list)
    user_visible_summary: str | None = None
