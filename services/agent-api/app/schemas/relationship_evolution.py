"""Typed contracts for reviewed Relationship evolution."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RelationshipCommitRequest(_StrictRequest):
    expected_revision: int = Field(ge=0)
    reason: str = Field(min_length=1, max_length=1000)


class RelationshipRejectRequest(_StrictRequest):
    reason: str = Field(min_length=1, max_length=1000)


class RelationshipCorrectionRequest(_StrictRequest):
    expected_revision: int = Field(ge=1)
    reason: str = Field(min_length=1, max_length=1000)


class RelationshipSignalRead(BaseModel):
    dimension: Literal[
        "familiarity", "understanding", "collaboration", "trust",
        "emotional_closeness", "boundary_awareness", "continuity",
    ]
    direction: Literal["increase", "decrease"]
