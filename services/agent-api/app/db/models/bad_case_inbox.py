"""Agent execution bad case inbox models."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class BadCaseInboxItem(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "bad_case_inbox_items"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"))
    message_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("messages.id"))
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"))
    replay_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("agent_run_replays.id"))
    source_type: Mapped[str] = mapped_column(Text, nullable=False)
    case_type: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(Text, default="medium")
    status: Mapped[str] = mapped_column(Text, default="open")
    evidence_summary: Mapped[str | None] = mapped_column(Text)
    suggested_fix: Mapped[str | None] = mapped_column(Text)
    created_regression_case_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BadCaseLink(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "bad_case_links"

    bad_case_inbox_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("bad_case_inbox_items.id", ondelete="CASCADE"))
    link_type: Mapped[str] = mapped_column(Text, nullable=False)
    linked_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    relation: Mapped[str] = mapped_column(Text, default="evidence")
    note: Mapped[str | None] = mapped_column(Text)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class BadCaseTriageEvent(Base, UUIDMixin, MetadataMixin):
    __tablename__ = "bad_case_triage_events"

    bad_case_inbox_item_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("bad_case_inbox_items.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    previous_status: Mapped[str | None] = mapped_column(Text)
    new_status: Mapped[str] = mapped_column(Text, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class BadCaseCluster(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "bad_case_clusters"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    case_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="active")
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    summary: Mapped[str | None] = mapped_column(Text)
    representative_item_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("bad_case_inbox_items.id"))
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
