"""Agent execution strategy learning schemas."""

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field


LearningMode = Literal["disabled", "shadow", "assistive", "active"]


class RerankerTrainingExampleCreate(BaseModel):
    memory_id: uuid.UUID | None = None
    feedback_event_id: uuid.UUID | None = None
    memory_usage_event_id: uuid.UUID | None = None
    label: float = Field(ge=-1, le=1)
    feature_json: dict[str, Any] = Field(default_factory=dict)
    source_type: str = "feedback"


class MemoryRerankerRunRead(BaseModel):
    id: uuid.UUID
    trace_run_id: uuid.UUID | None = None
    learning_mode: LearningMode = "shadow"
    candidate_memory_ids: list[uuid.UUID] = Field(default_factory=list)
    selected_memory_ids: list[uuid.UUID] = Field(default_factory=list)
    score_json: dict[str, Any] = Field(default_factory=dict)
    explanation_json: dict[str, Any] = Field(default_factory=dict)
    status: Literal["created", "completed", "failed", "cancelled"] = "created"

    model_config = {"from_attributes": True}


class PresencePolicyFeedbackSampleCreate(BaseModel):
    presence_opportunity_id: uuid.UUID | None = None
    feedback_event_id: uuid.UUID | None = None
    action_taken: str
    reward: float = Field(default=0.0, ge=-1, le=1)
    feature_json: dict[str, Any] = Field(default_factory=dict)


class PresencePolicyRunRead(BaseModel):
    id: uuid.UUID
    trace_run_id: uuid.UUID | None = None
    presence_opportunity_id: uuid.UUID | None = None
    learning_mode: LearningMode = "shadow"
    action_space: list[str] = Field(default_factory=lambda: ["no_show", "defer", "queue"])
    selected_action: str = "no_show"
    reward_prediction: float | None = Field(default=None, ge=-1, le=1)
    explanation_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}
