"""Agent execution provider and prompt schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class LlmProviderConfigCreate(BaseModel):
    provider_name: str
    provider_type: Literal["llm", "embedding", "reranker", "vision", "tool"] = "llm"
    status: Literal["enabled", "disabled", "degraded", "failed"] = "enabled"
    base_url: str | None = None
    env_key_name: str | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)


class LlmProviderConfigRead(LlmProviderConfigCreate):
    id: uuid.UUID
    user_id: uuid.UUID | None = None
    companion_id: uuid.UUID | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class LlmModelConfigCreate(BaseModel):
    provider_config_id: uuid.UUID
    model_name: str
    model_role: Literal["response_generation", "embedding", "reranker", "judge", "summary"] = "response_generation"
    status: Literal["enabled", "disabled", "degraded", "failed"] = "enabled"
    temperature: float | None = None
    max_tokens: int | None = None
    config_json: dict[str, Any] = Field(default_factory=dict)


class PromptVersionCreate(BaseModel):
    prompt_key: str
    version: str
    status: Literal["draft", "active", "archived", "deprecated"] = "draft"
    content: str
    change_note: str | None = None


class LlmCallRecordRead(BaseModel):
    id: uuid.UUID
    trace_run_id: uuid.UUID | None = None
    status: Literal["queued", "running", "succeeded", "failed", "cancelled", "rate_limited", "fallback_used"] = "queued"
    fallback_used: bool = False
    latency_ms: int | None = None
    token_input: int | None = None
    token_output: int | None = None

    model_config = {"from_attributes": True}
