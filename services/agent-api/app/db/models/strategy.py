"""Agent execution strategy learning models."""

import uuid
from datetime import datetime

from sqlalchemy import ARRAY, DateTime, Double, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class RerankerTrainingExample(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "reranker_training_examples"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    memory_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id"))
    feedback_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("feedback_events.id"))
    memory_usage_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memory_usage_events.id"))
    label: Mapped[float] = mapped_column(Double, nullable=False)
    feature_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    source_type: Mapped[str] = mapped_column(Text, default="feedback")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class MemoryRerankerRun(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "memory_reranker_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"))
    learning_mode: Mapped[str] = mapped_column(Text, default="shadow")
    candidate_memory_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}")
    selected_memory_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, server_default="{}")
    score_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    explanation_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(Text, default="completed")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PresencePolicyFeedbackSample(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "presence_policy_feedback_samples"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    presence_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("presence_opportunities.id"))
    feedback_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("feedback_events.id"))
    action_taken: Mapped[str] = mapped_column(Text, nullable=False)
    reward: Mapped[float] = mapped_column(Double, default=0.0)
    feature_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PresencePolicyRun(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "presence_policy_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"))
    presence_opportunity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("presence_opportunities.id"))
    learning_mode: Mapped[str] = mapped_column(Text, default="shadow")
    action_space: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list, server_default="{no_show,defer,queue}")
    selected_action: Mapped[str] = mapped_column(Text, default="no_show")
    reward_prediction: Mapped[float | None] = mapped_column(Double)
    explanation_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
