"""User-safe Companion trace projections."""

import uuid
from typing import Any

from pydantic import BaseModel, Field


class CompanionTraceSection(BaseModel):
    step_name: str | None = None
    status: str | None = None
    decision: str | None = None
    summary: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class CompanionTraceSummary(BaseModel):
    trace_run_id: uuid.UUID | None = None
    narrative_summary: str | None = None
    companion_consistency_score: float | None = None
    co_presence_boundary_ok: bool | None = None
    shared_memory_review_required: bool | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class CompanionTraceDetail(BaseModel):
    summary: CompanionTraceSummary
    companion_identity_trace: CompanionTraceSection = Field(default_factory=CompanionTraceSection)
    persona_profile_trace: CompanionTraceSection = Field(default_factory=CompanionTraceSection)
    relationship_contract_trace: CompanionTraceSection = Field(default_factory=CompanionTraceSection)
    co_presence_session_trace: CompanionTraceSection = Field(default_factory=CompanionTraceSection)
    participant_awareness_trace: CompanionTraceSection = Field(default_factory=CompanionTraceSection)
    shared_scene_trace: CompanionTraceSection = Field(default_factory=CompanionTraceSection)
    companion_memory_scope_trace: CompanionTraceSection = Field(default_factory=CompanionTraceSection)
    shared_memory_candidate_trace: CompanionTraceSection = Field(default_factory=CompanionTraceSection)
    cross_companion_boundary_trace: CompanionTraceSection = Field(default_factory=CompanionTraceSection)
    persona_guard_trace: CompanionTraceSection = Field(default_factory=CompanionTraceSection)
    mutual_presence_trace: CompanionTraceSection = Field(default_factory=CompanionTraceSection)
    delegated_execution_trace: CompanionTraceSection = Field(default_factory=CompanionTraceSection)
    provider_trace: CompanionTraceSection = Field(default_factory=CompanionTraceSection)
    tool_file_evidence_trace: CompanionTraceSection = Field(default_factory=CompanionTraceSection)
