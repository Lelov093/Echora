"""Agent execution project planning models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Double, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class ProjectMilestone(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "project_milestones"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="planned")
    target_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    priority: Mapped[float] = mapped_column(Double, default=0.5)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectTask(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "project_tasks"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    milestone_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("project_milestones.id"))
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text, default="todo")
    priority: Mapped[float] = mapped_column(Double, default=0.5)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_summary: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ProjectTaskEvent(Base, UUIDMixin, MetadataMixin):
    __tablename__ = "project_task_events"

    project_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project_tasks.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    previous_status: Mapped[str | None] = mapped_column(Text)
    new_status: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    event_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ProjectTaskEvidenceLink(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "project_task_evidence_links"

    project_task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("project_tasks.id", ondelete="CASCADE"), nullable=False)
    evidence_type: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    relevance_score: Mapped[float] = mapped_column(Double, default=0.5)
    note: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
