"""Agent execution replay models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Double, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class AgentRunReplay(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "agent_run_replays"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"))
    replay_type: Mapped[str] = mapped_column(Text, default="static")
    status: Mapped[str] = mapped_column(Text, default="created")
    title: Mapped[str | None] = mapped_column(Text)
    input_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    memory_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    file_context_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    tool_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    trace_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    output_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    summary: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TraceReplaySession(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "trace_replay_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"))
    agent_run_replay_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_run_replays.id"))
    status: Mapped[str] = mapped_column(Text, default="created")
    replay_mode: Mapped[str] = mapped_column(Text, default="static")
    result_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    elapsed_ms: Mapped[int | None] = mapped_column(Integer)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ReplayAnnotation(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "replay_annotations"

    agent_run_replay_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_run_replays.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    annotation_type: Mapped[str] = mapped_column(Text, nullable=False)
    target_ref_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
