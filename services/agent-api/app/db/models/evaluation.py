"""Agent execution evaluation models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Double, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class EvaluationDataset(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "evaluation_datasets"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    dataset_type: Mapped[str] = mapped_column(Text, default="manual")
    status: Mapped[str] = mapped_column(Text, default="active")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationCase(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "evaluation_cases"

    dataset_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evaluation_datasets.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    case_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    input_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    expected_behavior: Mapped[str | None] = mapped_column(Text)
    expected_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    evidence_refs: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    status: Mapped[str] = mapped_column(Text, default="active")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationRun(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "evaluation_runs"

    dataset_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("evaluation_datasets.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending")
    judge_type: Mapped[str] = mapped_column(Text, default="manual")
    model_config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_trace_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trace_runs.id")
    )
    source_domain: Mapped[str | None] = mapped_column(Text)
    source_entity_type: Mapped[str | None] = mapped_column(Text)
    source_entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    source_entity_revision: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    feedback_revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    trigger_type: Mapped[str | None] = mapped_column(Text)
    aggregate_score: Mapped[float | None] = mapped_column(Double)
    result_summary_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, server_default="3")
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(Text)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationResult(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "evaluation_results"

    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False)
    evaluation_case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("evaluation_cases.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"))
    replay_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_run_replays.id"))
    status: Mapped[str] = mapped_column(Text, default="needs_review")
    score: Mapped[float | None] = mapped_column(Double)
    judge_reason: Mapped[str | None] = mapped_column(Text)
    output_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    expected_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_bad_case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("bad_cases.id"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class EvaluationMetric(Base, UUIDMixin):
    __tablename__ = "evaluation_metrics"

    evaluation_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("evaluation_runs.id", ondelete="CASCADE"), nullable=False)
    metric_name: Mapped[str] = mapped_column(Text, nullable=False)
    metric_value: Mapped[float] = mapped_column(Double, nullable=False)
    metric_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
