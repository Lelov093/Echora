"""User-owned controls for Companion growth suggestions."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


GrowthSuggestionType = Literal[
    "understanding_update",
    "preference",
    "relationship",
    "correction",
    "behavior",
    "communication_style",
    "self_narrative",
    "boundary_update",
]


class GrowthSuggestionPolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    suggestions_enabled: bool
    paused_types: list[GrowthSuggestionType] = Field(default_factory=list)
    expected_updated_at: datetime | None = None


class GrowthCandidateEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str = Field(min_length=1, max_length=3000)
    reason: str = Field(min_length=1, max_length=1000)
