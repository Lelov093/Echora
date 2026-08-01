"""Companion companion presence / mutual presence ORM models."""

import uuid

from sqlalchemy import Boolean, Double, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class MutualPresencePolicyRun(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "mutual_presence_policy_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    primary_companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    shared_scene_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_scenes.id"), nullable=True
    )
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True)
    source_presence_policy_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presence_policy_runs.id"), nullable=True
    )
    presence_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presence_opportunities.id"), nullable=True
    )
    policy_scope: Mapped[str] = mapped_column(Text, default="companion_presence")
    learning_mode: Mapped[str] = mapped_column(Text, default="shadow")
    selected_action: Mapped[str] = mapped_column(Text, default="queue")
    policy_status: Mapped[str] = mapped_column(Text, default="created")
    reward_prediction: Mapped[float | None] = mapped_column(Double, nullable=True)
    mutuality_score: Mapped[float] = mapped_column(Double, default=0.5)
    interruption_risk: Mapped[float] = mapped_column(Double, default=0.0)
    presence_value: Mapped[float] = mapped_column(Double, default=0.5)
    explanation_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    boundary_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    signal_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class CompanionPresenceOpportunity(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_presence_opportunities"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    base_presence_opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presence_opportunities.id"), nullable=False
    )
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    shared_scene_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_scenes.id"), nullable=True
    )
    mutual_presence_policy_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mutual_presence_policy_runs.id"), nullable=True
    )
    opportunity_origin: Mapped[str] = mapped_column(Text, default="companion_private")
    presence_mode: Mapped[str] = mapped_column(Text, default="solo_checkin")
    opportunity_status: Mapped[str] = mapped_column(Text, default="queued")
    recommended_surface: Mapped[str] = mapped_column(Text, default="hub_queue")
    requires_user_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    rationale_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    presence_context_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class CoPresenceOpportunity(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "co_presence_opportunities"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    primary_companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    base_presence_opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presence_opportunities.id"), nullable=False
    )
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    shared_scene_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_scenes.id"), nullable=True
    )
    target_companion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True
    )
    mutual_presence_policy_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mutual_presence_policy_runs.id"), nullable=True
    )
    opportunity_type: Mapped[str] = mapped_column(Text, default="invite_active_companion")
    opportunity_status: Mapped[str] = mapped_column(Text, default="queued")
    target_role: Mapped[str] = mapped_column(Text, default="active_companion")
    recommended_surface: Mapped[str] = mapped_column(Text, default="hub_queue")
    requires_user_confirmation: Mapped[bool] = mapped_column(Boolean, default=True)
    rationale_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    boundary_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class CompanionPresenceFeedbackEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_presence_feedback_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    base_presence_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("presence_opportunities.id"), nullable=True
    )
    companion_presence_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companion_presence_opportunities.id"), nullable=True
    )
    co_presence_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_opportunities.id"), nullable=True
    )
    mutual_presence_policy_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("mutual_presence_policy_runs.id"), nullable=True
    )
    feedback_event_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("feedback_events.id"), nullable=True
    )
    feedback_type: Mapped[str] = mapped_column(Text, default="accept")
    feedback_source: Mapped[str] = mapped_column(Text, default="user")
    feedback_strength: Mapped[float | None] = mapped_column(Double, nullable=True)
    feedback_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    feedback_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


__all__ = [
    "MutualPresencePolicyRun",
    "CompanionPresenceOpportunity",
    "CoPresenceOpportunity",
    "CompanionPresenceFeedbackEvent",
]
