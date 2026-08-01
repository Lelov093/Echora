"""GrowthCandidate and GrowthRecord models."""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, Double, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDMixin, TimestampMixin, MetadataMixin, Base


class GrowthCandidate(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "growth_candidates"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True
    )

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_memory_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    evidence_message_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )

    confidence: Mapped[float] = mapped_column(Double, default=0.5)
    evidence_score: Mapped[float] = mapped_column(Double, default=0.0)
    impact_scope: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, server_default="{}"
    )
    risk_level: Mapped[str] = mapped_column(String(20), default="low")
    requires_user_review: Mapped[bool] = mapped_column(Boolean, default=True)

    status: Mapped[str] = mapped_column(String(50), default="candidate")
    committed_growth_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )

    score_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # ── Continuity: feedback / review ──────────────────────────────────
    review_batch_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("review_batches.id"), nullable=True
    )
    source_abstraction_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memory_abstraction_candidates.id"), nullable=True
    )
    feedback_score: Mapped[float] = mapped_column(Double, default=0.0)
    positive_feedback_count: Mapped[int] = mapped_column(Integer, default=0)
    negative_feedback_count: Mapped[int] = mapped_column(Integer, default=0)
    impact_preview_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    profile_patch_preview: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    user_feedback_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    calibration_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class GrowthRecord(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "growth_records"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )
    source_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("growth_candidates.id"), nullable=True
    )

    type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_memory_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    evidence_message_ids: Mapped[list[uuid.UUID]] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )

    impact_scope: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, server_default="{}"
    )
    impact_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    applied_to_profile: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[str] = mapped_column(String(50), default="committed")
    reverted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revert_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # ── Continuity: abstraction / impact ───────────────────────────────
    source_abstraction_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memory_abstraction_candidates.id"), nullable=True
    )
    profile_patch_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    profile_version_before: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    profile_version_after: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    downstream_trace_run_ids: Mapped[list] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    downstream_memory_ids: Mapped[list] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    downstream_presence_opportunity_ids: Mapped[list] = mapped_column(
        ARRAY(UUID(as_uuid=True)), default=list, server_default="{}"
    )
    feedback_score: Mapped[float] = mapped_column(Double, default=0.0)
    last_feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revert_impact_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
