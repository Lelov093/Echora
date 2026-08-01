"""Agent execution tool schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


ToolType = Literal["internal", "local_command", "http_api", "simulation", "manual"]
RiskLevel = Literal["low", "medium", "high", "critical"]
PermissionPolicy = Literal["not_required", "ask_once", "ask_every_time", "disabled"]
ToolRunStatus = Literal[
    "planned", "awaiting_input", "awaiting_confirmation", "queued", "running",
    "retry_scheduled", "succeeded", "failed", "cancelled", "blocked", "timed_out",
]


class ToolDefinitionCreate(BaseModel):
    name: str
    display_name: str | None = None
    description: str | None = None
    tool_type: ToolType = "internal"
    risk_level: RiskLevel = "medium"
    permission_policy: PermissionPolicy = "ask_every_time"
    input_schema_json: dict[str, Any] = Field(default_factory=dict)
    output_schema_json: dict[str, Any] = Field(default_factory=dict)
    config_json: dict[str, Any] = Field(default_factory=dict)


class ToolDefinitionRead(ToolDefinitionCreate):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    companion_id: uuid.UUID | None = None
    is_enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ToolDefinitionUpdate(BaseModel):
    display_name: str | None = None
    description: str | None = None
    risk_level: RiskLevel | None = None
    permission_policy: PermissionPolicy | None = None
    is_enabled: bool | None = None
    config_json: dict[str, Any] | None = None


class ToolPermissionCreate(BaseModel):
    tool_definition_id: uuid.UUID
    policy: PermissionPolicy = "ask_every_time"
    reason: str | None = None
    scope_json: dict[str, Any] = Field(default_factory=dict)


class ToolPermissionRead(ToolPermissionCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    status: Literal["active", "denied", "revoked", "expired"] = "active"
    allowed_until: datetime | None = None

    model_config = {"from_attributes": True}


class ToolRunCreate(BaseModel):
    companion_id: uuid.UUID
    tool_definition_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    trace_run_id: uuid.UUID | None = None
    input_json: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, min_length=8, max_length=160)


class ToolRunRead(ToolRunCreate):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    status: ToolRunStatus = "planned"
    permission_required: bool = True
    permission_granted: bool = False
    output_json: dict[str, Any] = Field(default_factory=dict)
    error_json: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[dict[str, Any]] = Field(default_factory=list)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    elapsed_ms: int | None = None
    capability: str | None = None
    confirmation_required: bool = False
    confirmation_summary: str | None = None
    attempt_count: int = 0
    max_attempts: int = 3
    timeout_seconds: int = 20
    terminal_reason: str | None = None

    model_config = {"from_attributes": True}


class ToolRunActionRequest(BaseModel):
    companion_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    reason: str | None = Field(default=None, max_length=500)


class ToolPermissionUpdate(BaseModel):
    companion_id: uuid.UUID
    policy: PermissionPolicy | None = None
    status: Literal["active", "denied", "revoked", "expired"] | None = None
    allowed_until: datetime | None = None
    reason: str | None = Field(default=None, max_length=500)
    scope_json: dict[str, Any] | None = None


class ToolPermissionSet(BaseModel):
    companion_id: uuid.UUID
    policy: PermissionPolicy
    reason: str | None = Field(default=None, max_length=500)
