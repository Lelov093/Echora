"""Continuity Review Batch schemas."""

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


BatchType = Literal[
    "memory_candidates", "growth_candidates",
    "abstraction_candidates", "presence_opportunities", "mixed_review",
]

BatchStatus = Literal["open", "completed", "cancelled", "expired"]


class ReviewBatchCreate(BaseModel):
    companion_id: uuid.UUID
    batch_type: BatchType
    title: str | None = None
    description: str | None = None
    conversation_id: uuid.UUID | None = None
    item_refs: list[dict[str, Any]] = Field(default_factory=list)


class ReviewBatchRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    conversation_id: uuid.UUID | None = None
    batch_type: BatchType
    title: str | None = None
    description: str | None = None
    item_count: int = 0
    accepted_count: int = 0
    edited_count: int = 0
    rejected_count: int = 0
    skipped_count: int = 0
    status: BatchStatus = "open"
    completed_at: datetime | None = None
    item_refs: list[dict[str, Any]] = Field(default_factory=list)
    result_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class ReviewBatchListQuery(BaseModel):
    companion_id: uuid.UUID | None = None
    batch_type: BatchType | None = None
    status: BatchStatus | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ReviewBatchItemAction(BaseModel):
    item_ref_id: uuid.UUID
    item_type: Literal["memory_candidate", "growth_candidate", "abstraction_candidate", "presence_opportunity"]
    decision: Literal["accept", "edit_accept", "reject", "skip"]
    edited_content: str | None = None
    note: str | None = None


class ApplyReviewBatchRequest(BaseModel):
    actions: list[ReviewBatchItemAction] = Field(default_factory=list)
    batch_id: uuid.UUID | None = None
    complete_batch: bool = True
    note: str | None = None


class ApplyReviewBatchResponse(BaseModel):
    batch_id: uuid.UUID
    accepted: int = 0
    edited: int = 0
    rejected: int = 0
    skipped: int = 0
    effects: list[dict[str, Any]] = Field(default_factory=list)
    batch_status: BatchStatus = "completed"
