"""Typed product contracts for saved Memory and Companion Presence policy."""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SavedMemoryCreateRequest(_StrictRequest):
    user_id: uuid.UUID
    companion_id: uuid.UUID
    content: str = Field(min_length=1, max_length=100000)
    summary: str | None = Field(default=None, max_length=10000)
    type: Literal[
        "fact", "preference", "goal", "episodic", "correction", "relationship",
        "emotional", "self", "project", "creative", "system",
    ] = "episodic"
    state: Literal["active", "dormant", "archived"] = "active"
    importance: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=0.5, ge=0, le=1)
    consent_status: str = Field(default="user_confirmed", max_length=50)


class SavedMemoryCorrectionRequest(_StrictRequest):
    content: str = Field(min_length=1, max_length=100000)
    summary: str | None = Field(default=None, max_length=10000)
    reason: str = Field(min_length=1, max_length=1000)
    expected_revision: int = Field(ge=1)


class SavedMemoryRevisionRestoreRequest(_StrictRequest):
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class MemoryCandidateMergeRequest(_StrictRequest):
    companion_id: uuid.UUID
    target_memory_id: uuid.UUID
    expected_revision: int = Field(ge=1)
    merged_content: str = Field(min_length=1, max_length=100000)
    reason: str = Field(min_length=1, max_length=1000)


class ContextDocumentCorrectionRequest(_StrictRequest):
    expected_version: int = Field(ge=1)
    content: str = Field(min_length=1, max_length=10000)
    reason: str = Field(min_length=1, max_length=1000)


class ContextDocumentVersionRequest(_StrictRequest):
    expected_version: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class ContextDocumentRefreshRequest(_StrictRequest):
    user_id: uuid.UUID
    conversation_id: uuid.UUID
    force: bool = False
    reason: str = Field(default="user_requested_refresh", min_length=1, max_length=1000)


class PresencePolicyUpdateRequest(_StrictRequest):
    proactive_level: Literal["off", "low", "medium", "high"] | None = None
    notification_surface: str | None = Field(default=None, max_length=50)
    allow_proactive_presence: bool | None = None
    suppressed_presence_types: list[str] | None = None
    quiet_hours: dict[str, Any] | None = None
    suppressed_presence_rules: list[dict[str, Any]] | None = None
    max_presence_per_day: int | None = Field(default=None, ge=0, le=100)
    min_presence_interval_minutes: int | None = Field(default=None, ge=0, le=10080)
    meaningful_silence_enabled: bool | None = None
