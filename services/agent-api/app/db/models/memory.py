"""Memory and MemoryCandidate models.

memories is the core table of Echora's cognitive memory system.
"""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Double, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from pgvector.sqlalchemy import Vector
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDMixin, TimestampMixin, SoftDeleteMixin, MetadataMixin, Base


class Memory(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, MetadataMixin):
    __tablename__ = "memories"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    owner_companion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )
    shared_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_episodic_memories.id"), nullable=True
    )

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    state: Mapped[str] = mapped_column(String(50), default="active")
    visibility: Mapped[str] = mapped_column(String(50), default="user_visible")
    consent_status: Mapped[str] = mapped_column(String(50), default="auto")
    memory_scope_type: Mapped[str] = mapped_column(String(50), default="legacy_private")
    memory_layer: Mapped[str] = mapped_column(
        String(50), default="companion_private"
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_message_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    source_modality: Mapped[str] = mapped_column(String(20), default="text")

    # ── scoring fields ───────────────────────────────────────────
    importance: Mapped[float] = mapped_column(Double, default=0.5)
    confidence: Mapped[float] = mapped_column(Double, default=0.5)
    emotional_intensity: Mapped[float] = mapped_column(Double, default=0.0)
    goal_relevance: Mapped[float] = mapped_column(Double, default=0.0)
    relationship_impact: Mapped[float] = mapped_column(Double, default=0.0)
    correction_value: Mapped[float] = mapped_column(Double, default=0.0)

    # ── lifecycle fields ─────────────────────────────────────────
    memory_strength: Mapped[float] = mapped_column(Double, default=0.5)
    decay_rate: Mapped[float] = mapped_column(Double, default=0.01)
    half_life_days: Mapped[float | None] = mapped_column(Double, nullable=True)
    base_half_life_days: Mapped[float | None] = mapped_column(Double, nullable=True)
    reactivation_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reactivated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    strength_anchor_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_maintenance_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    lifecycle_algorithm_version: Mapped[str] = mapped_column(
        Text, default="core-memory-lifecycle-v1"
    )

    # Personalized lifecycle calibration state.
    confidence_prior_alpha: Mapped[float] = mapped_column(Double, default=2.0)
    confidence_prior_beta: Mapped[float] = mapped_column(Double, default=2.0)
    confidence_alpha: Mapped[float] = mapped_column(Double, default=2.0)
    confidence_beta: Mapped[float] = mapped_column(Double, default=2.0)
    successful_recall_count: Mapped[int] = mapped_column(Integer, default=0)
    growth_use_count: Mapped[int] = mapped_column(Integer, default=0)
    presence_use_count: Mapped[int] = mapped_column(Integer, default=0)
    repeated_topic_count: Mapped[int] = mapped_column(Integer, default=0)
    calibrated_positive_count: Mapped[int] = mapped_column(Integer, default=0)
    calibrated_helpful_count: Mapped[int] = mapped_column(Integer, default=0)
    calibrated_irrelevant_count: Mapped[int] = mapped_column(Integer, default=0)
    calibrated_outdated_count: Mapped[int] = mapped_column(Integer, default=0)
    calibrated_wrong_count: Mapped[int] = mapped_column(Integer, default=0)

    # ── feedback fields ──────────────────────────────────────────
    positive_confirmations: Mapped[int] = mapped_column(Integer, default=0)
    correction_count: Mapped[int] = mapped_column(Integer, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, default=0)
    usage_feedback: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    helpful_feedback: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    mode_specific_feedback: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    # ── Continuity: feedback / timeline / impact ──────────────────────
    last_feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_in_response_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_in_growth_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_used_in_presence_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    feedback_score: Mapped[float] = mapped_column(Double, default=0.0)
    helpful_count: Mapped[int] = mapped_column(Integer, default=0)
    irrelevant_count: Mapped[int] = mapped_column(Integer, default=0)
    outdated_count: Mapped[int] = mapped_column(Integer, default=0)
    wrong_count: Mapped[int] = mapped_column(Integer, default=0)
    impact_summary: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    lifecycle_summary: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    visibility_policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    # ── Continuity: abstraction ───────────────────────────────────────
    abstraction_level: Mapped[int] = mapped_column(Integer, default=0)
    source_abstraction_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memory_abstraction_candidates.id"), nullable=True
    )
    parent_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id"), nullable=True
    )

    # ── vector ───────────────────────────────────────────────────
    embedding = mapped_column(Vector(1024), nullable=True)


class MemoryCandidate(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "memory_candidates"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )
    proposed_owner_companion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )
    proposed_shared_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_episodic_memories.id"), nullable=True
    )

    source_message_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_type: Mapped[str] = mapped_column(String(50), default="episodic")

    importance: Mapped[float] = mapped_column(Double, default=0.5)
    confidence: Mapped[float] = mapped_column(Double, default=0.5)
    emotional_intensity: Mapped[float] = mapped_column(Double, default=0.0)
    goal_relevance: Mapped[float] = mapped_column(Double, default=0.0)
    relationship_impact: Mapped[float] = mapped_column(Double, default=0.0)
    correction_value: Mapped[float] = mapped_column(Double, default=0.0)
    novelty: Mapped[float] = mapped_column(Double, default=0.0)
    recurrence: Mapped[float] = mapped_column(Double, default=0.0)
    triviality: Mapped[float] = mapped_column(Double, default=0.0)
    sensitivity_risk: Mapped[float] = mapped_column(Double, default=0.0)

    score: Mapped[float] = mapped_column(Double, default=0.0)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    needs_user_confirmation: Mapped[bool] = mapped_column(default=True)
    status: Mapped[str] = mapped_column(String(50), default="pending")
    requires_companion_memory_review: Mapped[bool] = mapped_column(default=False)

    accepted_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id"), nullable=True
    )
    edited_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_label: Mapped[str | None] = mapped_column(String(50), nullable=True)

    score_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    embedding = mapped_column(Vector(1024), nullable=True)

    # ── Continuity: review batch / abstraction ───────────────────────
    review_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_batches.id"), nullable=True
    )
    review_priority: Mapped[float] = mapped_column(Double, default=0.5)
    user_feedback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    abstraction_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memory_abstraction_candidates.id"), nullable=True
    )
    lifecycle_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memory_lifecycle_events.id"), nullable=True
    )
    suggested_half_life_days: Mapped[float | None] = mapped_column(Double, nullable=True)
    suggested_confidence_after_beta: Mapped[float | None] = mapped_column(Double, nullable=True)
    calibration_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
