"""Typed product contracts for Conversation and Message lifecycle operations."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ReasoningMode = Literal["auto", "fast", "thinking", "deep_thinking"]


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ConversationCreateRequest(_StrictRequest):
    user_id: uuid.UUID
    companion_id: uuid.UUID
    title: str = Field(default="New Conversation", min_length=1, max_length=500)
    mode_key: Literal["project", "creative", "daily", "learning", "game", "character", "virtual_world"] = "daily"
    retention_mode: Literal["standard", "temporary"] = "standard"
    cross_session_memory_enabled: bool = True
    reasoning_mode: ReasoningMode = "auto"


class ConversationUpdateRequest(_StrictRequest):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    mode_key: Literal["project", "creative", "daily", "learning", "game", "character", "virtual_world"] | None = None
    current_topic: str | None = Field(default=None, max_length=4000)
    current_goal: str | None = Field(default=None, max_length=4000)
    cross_session_memory_enabled: bool | None = None
    reasoning_mode: ReasoningMode | None = None


class MessageCreateRequest(_StrictRequest):
    content: str = Field(min_length=1, max_length=100000)
    content_format: Literal["text", "markdown"] = "text"
    source_modality: Literal["text"] = "text"


class MessageCorrectionRequest(_StrictRequest):
    content: str = Field(min_length=1, max_length=100000)
    reason: str | None = Field(default=None, max_length=1000)


class ConversationTurnRetryRequest(_StrictRequest):
    companion_id: uuid.UUID


class ConversationTurnStartRequest(_StrictRequest):
    companion_id: uuid.UUID
    content: str = Field(min_length=1, max_length=100000)
    mode_key: Literal["project", "creative", "daily", "learning", "game", "character", "virtual_world"] | None = None
    idempotency_key: str = Field(min_length=1, max_length=200)
    continuation_of_trace_run_id: uuid.UUID | None = None
    reasoning_mode: ReasoningMode | None = None


class ConversationTurnCancelRequest(_StrictRequest):
    companion_id: uuid.UUID


class LifecycleReasonRequest(_StrictRequest):
    reason: str | None = Field(default=None, max_length=1000)


class ConversationPermanentDeleteRequest(_StrictRequest):
    confirmation_phrase: Literal["永久删除"]
