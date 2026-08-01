"""Durable bounded task planning and orchestration truth."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class ConversationTaskRun(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "conversation_task_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )
    source_message_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id"), nullable=False
    )
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trace_runs.id")
    )
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", nullable=False)
    acceptance_state: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False
    )
    plan_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    current_step_order: Mapped[int | None] = mapped_column(Integer)
    max_steps: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    max_replans: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    replan_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_tool_runs: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    tool_run_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_tokens: Mapped[int] = mapped_column(Integer, default=12000, nullable=False)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(240), nullable=False)
    stop_reason: Mapped[str | None] = mapped_column(Text)
    cancellation_requested: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    lease_owner: Mapped[str | None] = mapped_column(String(120))
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConversationTaskStep(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "conversation_task_steps"

    task_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation_task_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    executor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    capability: Mapped[str | None] = mapped_column(String(64))
    risk_level: Mapped[str] = mapped_column(
        String(16), default="low", nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default="pending", nullable=False
    )
    dependencies_json: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    input_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    output_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    error_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    acceptance_criteria_json: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    evidence_refs: Mapped[list] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    confirmation_required: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ConversationTaskStepAttempt(
    Base, UUIDMixin, TimestampMixin, MetadataMixin
):
    __tablename__ = "conversation_task_step_attempts"

    task_step_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation_task_steps.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    executor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="queued", nullable=False
    )
    tool_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tool_runs.id")
    )
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("trace_runs.id")
    )
    provider_name: Mapped[str | None] = mapped_column(String(80))
    model_name: Mapped[str | None] = mapped_column(String(160))
    input_summary: Mapped[str | None] = mapped_column(Text)
    observation_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    verification_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    error_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    token_usage_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)


class ConversationTaskPlanRevision(
    Base, UUIDMixin, TimestampMixin, MetadataMixin
):
    __tablename__ = "conversation_task_plan_revisions"

    task_run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation_task_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_version: Mapped[int | None] = mapped_column(Integer)
    trigger: Mapped[str] = mapped_column(String(64), nullable=False)
    goal: Mapped[str] = mapped_column(Text, nullable=False)
    plan_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    changes_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    approval_required: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )
    created_by: Mapped[str] = mapped_column(
        String(32), default="planner", nullable=False
    )
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("messages.id")
    )
