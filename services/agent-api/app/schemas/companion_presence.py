"""Companion companion presence / mutual presence schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MutualPresencePolicyRunRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    primary_companion_id: uuid.UUID
    co_presence_session_id: uuid.UUID | None = None
    shared_scene_id: uuid.UUID | None = None
    trace_run_id: uuid.UUID | None = None
    source_presence_policy_run_id: uuid.UUID | None = None
    presence_opportunity_id: uuid.UUID | None = None
    policy_scope: str
    learning_mode: str
    selected_action: str
    policy_status: str
    reward_prediction: float | None = None
    mutuality_score: float = 0.5
    interruption_risk: float = 0.0
    presence_value: float = 0.5
    explanation_json: dict[str, Any] = Field(default_factory=dict)
    boundary_json: dict[str, Any] = Field(default_factory=dict)
    signal_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanionPresenceOpportunityRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    base_presence_opportunity_id: uuid.UUID
    co_presence_session_id: uuid.UUID | None = None
    shared_scene_id: uuid.UUID | None = None
    mutual_presence_policy_run_id: uuid.UUID | None = None
    opportunity_origin: str
    presence_mode: str
    opportunity_status: str
    recommended_surface: str
    requires_user_confirmation: bool = False
    review_required: bool = False
    rationale_summary: str | None = None
    presence_context_json: dict[str, Any] = Field(default_factory=dict)
    policy_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class CoPresenceOpportunityRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    primary_companion_id: uuid.UUID
    base_presence_opportunity_id: uuid.UUID
    co_presence_session_id: uuid.UUID | None = None
    shared_scene_id: uuid.UUID | None = None
    target_companion_id: uuid.UUID | None = None
    mutual_presence_policy_run_id: uuid.UUID | None = None
    opportunity_type: str
    opportunity_status: str
    target_role: str
    recommended_surface: str
    requires_user_confirmation: bool = True
    rationale_summary: str | None = None
    boundary_json: dict[str, Any] = Field(default_factory=dict)
    policy_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class CompanionPresenceFeedbackEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    base_presence_opportunity_id: uuid.UUID | None = None
    companion_presence_opportunity_id: uuid.UUID | None = None
    co_presence_opportunity_id: uuid.UUID | None = None
    mutual_presence_policy_run_id: uuid.UUID | None = None
    feedback_event_id: uuid.UUID | None = None
    feedback_type: str
    feedback_source: str
    feedback_strength: float | None = None
    feedback_note: str | None = None
    feedback_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class MutualPresencePolicyRunCreate(BaseModel):
    primary_companion_id: uuid.UUID
    co_presence_session_id: uuid.UUID | None = None
    shared_scene_id: uuid.UUID | None = None
    trace_run_id: uuid.UUID | None = None
    source_presence_policy_run_id: uuid.UUID | None = None
    presence_opportunity_id: uuid.UUID | None = None
    policy_scope: str = "companion_presence"
    learning_mode: str = "assistive"
    selected_action: str = "queue"
    policy_status: str = "created"
    reward_prediction: float | None = None
    mutuality_score: float = 0.5
    interruption_risk: float = 0.0
    presence_value: float = 0.5
    explanation_json: dict[str, Any] = Field(default_factory=dict)
    boundary_json: dict[str, Any] = Field(default_factory=dict)
    signal_json: dict[str, Any] = Field(default_factory=dict)


class CompanionPresenceFeedbackEventCreate(BaseModel):
    companion_id: uuid.UUID
    base_presence_opportunity_id: uuid.UUID | None = None
    companion_presence_opportunity_id: uuid.UUID | None = None
    co_presence_opportunity_id: uuid.UUID | None = None
    mutual_presence_policy_run_id: uuid.UUID | None = None
    feedback_event_id: uuid.UUID | None = None
    feedback_type: str = "accept"
    feedback_source: str = "user"
    feedback_strength: float | None = None
    feedback_note: str | None = None
    feedback_json: dict[str, Any] = Field(default_factory=dict)

