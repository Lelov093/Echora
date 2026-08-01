"""Agent execution regression models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Double, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class RegressionCase(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "regression_cases"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    source_bad_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bad_case_inbox_items.id")
    )
    source_replay_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_run_replays.id"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    case_type: Mapped[str] = mapped_column(Text, default="manual")
    input_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    expected_behavior: Mapped[str] = mapped_column(Text, nullable=False)
    expected_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    status: Mapped[str] = mapped_column(Text, default="active")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RegressionRun(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "regression_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending")
    total_count: Mapped[int] = mapped_column(Integer, default=0)
    passed_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result_summary_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RegressionResult(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "regression_results"

    regression_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("regression_runs.id", ondelete="CASCADE"), nullable=False)
    regression_case_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("regression_cases.id"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"))
    replay_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_run_replays.id"))
    status: Mapped[str] = mapped_column(Text, default="needs_review")
    score: Mapped[float | None] = mapped_column(Double)
    actual_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    failure_reason: Mapped[str | None] = mapped_column(Text)
    created_bad_case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("bad_cases.id"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
