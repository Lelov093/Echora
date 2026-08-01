"""Companion persona growth / drift guard ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, Double, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class CompanionPersonaGrowthCandidate(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_persona_growth_candidates"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    source_growth_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("growth_candidates.id"), nullable=True
    )
    shared_experience_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_experience_records.id"), nullable=True
    )
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    source_trace_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True
    )
    growth_dimension: Mapped[str] = mapped_column(Text, default="persona_summary")
    impact_level: Mapped[str] = mapped_column(Text, default="medium")
    candidate_status: Mapped[str] = mapped_column(Text, default="pending_review")
    growth_summary: Mapped[str] = mapped_column(Text, default="")
    evidence_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    proposed_persona_patch_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    proposed_presence_patch_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    confidence: Mapped[float] = mapped_column(Double, default=0.5)
    evidence_score: Mapped[float] = mapped_column(Double, default=0.0)
    requires_user_review: Mapped[bool] = mapped_column(Boolean, default=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class CompanionPersonaGrowthEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_persona_growth_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    source_persona_growth_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companion_persona_growth_candidates.id"), nullable=True
    )
    source_growth_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("growth_records.id"), nullable=True
    )
    source_trace_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True
    )
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(Text, default="candidate_committed")
    impact_level: Mapped[str] = mapped_column(Text, default="medium")
    event_summary: Mapped[str] = mapped_column(Text, default="")
    applied_patch_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    evidence_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class CompanionPersonaDriftCheck(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_persona_drift_checks"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    source_trace_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True
    )
    source_growth_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("growth_candidates.id"), nullable=True
    )
    source_persona_growth_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companion_persona_growth_candidates.id"), nullable=True
    )
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    shared_scene_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_scenes.id"), nullable=True
    )
    drift_risk_level: Mapped[str] = mapped_column(Text, default="low")
    check_status: Mapped[str] = mapped_column(Text, default="pending")
    baseline_source: Mapped[str] = mapped_column(Text, default="persona_profile")
    drift_score: Mapped[float] = mapped_column(Double, default=0.0)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False)
    blocks_auto_apply: Mapped[bool] = mapped_column(Boolean, default=False)
    drift_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    recommendation_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class GroupPersonaConsistencyCheck(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "group_persona_consistency_checks"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    shared_scene_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_scenes.id"), nullable=True
    )
    source_trace_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True
    )
    consistency_scope: Mapped[str] = mapped_column(Text, default="co_presence_session")
    check_status: Mapped[str] = mapped_column(Text, default="pending")
    consistency_score: Mapped[float] = mapped_column(Double, default=0.0)
    affected_companion_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False)
    consistency_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    conflict_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    recommendation_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


__all__ = [
    "CompanionPersonaGrowthCandidate",
    "CompanionPersonaGrowthEvent",
    "CompanionPersonaDriftCheck",
    "GroupPersonaConsistencyCheck",
]
