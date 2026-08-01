"""Read-only contracts for the Companion-first frontend."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class WorkspaceCompanion(BaseModel):
    id: str
    name: str
    subtitle: str | None = None
    current_mode: str
    current_status: str | None = None
    current_focus: str | None = None


class WorkspaceIdentity(BaseModel):
    display_name: str
    identity_summary: str
    core_traits: list[str] = Field(default_factory=list)
    persona_summary: str
    persona_lock_level: str
    relationship_role: str
    relationship_summary: str


class WorkspaceBoundary(BaseModel):
    private_memory_default: str
    shared_memory_default: str
    cross_companion_read_policy: str
    private_to_shared_review_required: bool
    shared_to_private_review_required: bool
    cross_companion_review_required: bool


class WorkspaceContinuity(BaseModel):
    conversation_id: str | None = None
    current_topic: str | None = None
    current_goal: str | None = None
    current_phase: str | None = None
    last_assistant_summary: str | None = None
    suggested_next_steps: list[Any] = Field(default_factory=list)
    updated_at: datetime | None = None


class WorkspaceMemoryPreview(BaseModel):
    id: str
    type: str
    summary: str
    updated_at: datetime | None = None


class WorkspacePresencePreview(BaseModel):
    id: str
    type: str
    title: str
    message: str | None = None
    priority: float
    recommended_surface: str
    expires_at: datetime | None = None


class CompanionWorkspaceReadModel(BaseModel):
    companion: WorkspaceCompanion
    identity: WorkspaceIdentity
    boundary: WorkspaceBoundary
    continuity: WorkspaceContinuity | None = None
    relationship: dict[str, Any] | None = None
    recent_private_memories: list[WorkspaceMemoryPreview] = Field(default_factory=list)
    presence_preview: list[WorkspacePresencePreview] = Field(default_factory=list)
    review_counts: dict[str, int] = Field(default_factory=dict)


class ChronicleItem(BaseModel):
    id: str
    companion_id: str
    kind: str
    occurred_at: datetime
    title: str
    summary: str
    source_id: str | None = None
    review_status: str | None = None
    trace_id: str | None = None


class CompanionChronicleReadModel(BaseModel):
    companion_id: str
    items: list[ChronicleItem]
    total: int
    limit: int
    offset: int


ReviewKind = Literal[
    "memory", "growth", "persona_growth", "private_to_shared",
    "shared_to_private", "cross_companion", "channel", "realtime_shared",
]


class ReviewInboxItem(BaseModel):
    id: str
    companion_id: str
    kind: ReviewKind
    created_at: datetime
    title: str
    summary: str
    status: str
    risk_level: str | None = None
    source_id: str | None = None


class CompanionReviewInboxReadModel(BaseModel):
    companion_id: str
    items: list[ReviewInboxItem]
    counts: dict[str, int]
    total: int
    limit: int
    offset: int
