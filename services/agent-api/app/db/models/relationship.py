"""RelationshipState and RelationshipEvent models."""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, Double, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDMixin, TimestampMixin, MetadataMixin, Base


class RelationshipState(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "relationship_states"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )

    familiarity: Mapped[float] = mapped_column(Double, default=0.0)
    understanding: Mapped[float] = mapped_column(Double, default=0.0)
    collaboration: Mapped[float] = mapped_column(Double, default=0.0)
    trust: Mapped[float] = mapped_column(Double, default=0.0)
    emotional_closeness: Mapped[float] = mapped_column(Double, default=0.0)
    boundary_awareness: Mapped[float] = mapped_column(Double, default=1.0)
    continuity: Mapped[float] = mapped_column(Double, default=0.0)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    belief_state_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    last_evidence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # ── Continuity: trends / explanations ──────────────────────────────
    familiarity_trend: Mapped[float] = mapped_column(Double, default=0.0)
    understanding_trend: Mapped[float] = mapped_column(Double, default=0.0)
    collaboration_trend: Mapped[float] = mapped_column(Double, default=0.0)
    trust_trend: Mapped[float] = mapped_column(Double, default=0.0)
    emotional_closeness_trend: Mapped[float] = mapped_column(Double, default=0.0)
    boundary_awareness_trend: Mapped[float] = mapped_column(Double, default=0.0)
    continuity_trend: Mapped[float] = mapped_column(Double, default=0.0)
    last_explanation_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("relationship_explanation_events.id"), nullable=True
    )
    explanation_summary: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("user_id", "companion_id"),
    )


class RelationshipEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "relationship_events"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    dimension: Mapped[str] = mapped_column(String(50), nullable=False)
    delta: Mapped[float] = mapped_column(Double, nullable=False)
    previous_value: Mapped[float | None] = mapped_column(Double, nullable=True)
    new_value: Mapped[float | None] = mapped_column(Double, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_memory_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    source_message_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("relationship_candidates.id"), nullable=True
    )
    state_revision_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("relationship_state_revisions.id"), nullable=True
    )
    event_group_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    supersedes_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("relationship_events.id"), nullable=True
    )
    operation: Mapped[str] = mapped_column(String(32), default="committed", nullable=False)
    evidence_weight: Mapped[float | None] = mapped_column(Double, nullable=True)
    posterior_variance: Mapped[float | None] = mapped_column(Double, nullable=True)


class RelationshipCandidate(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "relationship_candidates"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending", nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    dimension_signals_json: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    source_message_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}")
    source_memory_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}")
    evidence_quotes_json: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]", nullable=False)
    extraction_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    validation_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    evidence_score: Mapped[float] = mapped_column(Double, default=0.0, nullable=False)
    confidence: Mapped[float] = mapped_column(Double, default=0.0, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), default="medium", nullable=False)
    requires_user_review: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    expected_state_revision: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    provider_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    algorithm_version: Mapped[str] = mapped_column(String(100), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False, unique=True)
    committed_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RelationshipStateRevision(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "relationship_state_revisions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    relationship_state_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("relationship_states.id"), nullable=False)
    source_candidate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("relationship_candidates.id"), nullable=True)
    previous_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("relationship_state_revisions.id"), nullable=True)
    restored_from_revision_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("relationship_state_revisions.id"), nullable=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    snapshot_before_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    snapshot_after_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    belief_before_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    belief_after_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}", nullable=False)
    algorithm_version: Mapped[str] = mapped_column(String(100), nullable=False)

    __table_args__ = (UniqueConstraint("relationship_state_id", "revision", name="uq_relationship_state_revision"),)
