"""Agent execution tool execution models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Double, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class ToolDefinition(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "tool_definitions"

    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"))
    name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    tool_type: Mapped[str] = mapped_column(Text, default="internal")
    risk_level: Mapped[str] = mapped_column(Text, default="medium")
    permission_policy: Mapped[str] = mapped_column(Text, default="ask_every_time")
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    input_schema_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    output_schema_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    config_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ToolPermission(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "tool_permissions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    tool_definition_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tool_definitions.id"), nullable=False)
    policy: Mapped[str] = mapped_column(Text, default="ask_every_time")
    status: Mapped[str] = mapped_column(Text, default="active")
    allowed_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str | None] = mapped_column(Text)
    scope_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ToolRun(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "tool_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"))
    trace_step_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_steps.id"))
    tool_definition_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tool_definitions.id"))
    parent_tool_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tool_runs.id"))
    request_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id"))
    result_message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id"))
    requested_by: Mapped[str] = mapped_column(Text, default="agent")
    capability: Mapped[str | None] = mapped_column(Text)
    adapter_name: Mapped[str | None] = mapped_column(Text)
    adapter_version: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="planned")
    risk_level: Mapped[str] = mapped_column(Text, default="medium")
    permission_required: Mapped[bool] = mapped_column(Boolean, default=True)
    permission_granted: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmation_required: Mapped[bool] = mapped_column(Boolean, default=False)
    confirmation_summary: Mapped[str | None] = mapped_column(Text)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    confirmed_by: Mapped[str | None] = mapped_column(Text)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    input_schema_version: Mapped[str | None] = mapped_column(Text)
    output_schema_version: Mapped[str | None] = mapped_column(Text)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=20)
    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    lease_owner: Mapped[str | None] = mapped_column(Text)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    terminal_reason: Mapped[str | None] = mapped_column(Text)
    input_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    output_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    error_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    evidence_refs: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ToolRunStep(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "tool_run_steps"

    tool_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tool_runs.id", ondelete="CASCADE"), nullable=False)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    step_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending")
    input_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    output_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)


class ToolRunArtifact(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "tool_run_artifacts"

    tool_run_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tool_runs.id", ondelete="CASCADE"), nullable=False)
    artifact_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    uri: Mapped[str | None] = mapped_column(Text)
    content_text: Mapped[str | None] = mapped_column(Text)
    content_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ToolResource(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    """Durable local truth created by bounded daily tools."""

    __tablename__ = "tool_resources"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    source_tool_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("tool_runs.id"))
    resource_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="active")
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timezone_name: Mapped[str | None] = mapped_column(Text)
    resource_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
