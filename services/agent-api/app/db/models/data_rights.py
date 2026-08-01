"""Durable Companion deletion lifecycle and resumable purge scope."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class CompanionDeletionRequest(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_deletion_requests"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # Deliberately not a foreign key: the final proof must survive removal of
    # the Companion row. It is cleared after successful purge.
    companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    companion_scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="trash", nullable=False)
    deletion_mode: Mapped[str] = mapped_column(String(24), nullable=False)
    previous_companion_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    current_stage: Mapped[str] = mapped_column(String(80), default="recovery_window", nullable=False)
    restore_snapshot_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    affected_counts_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    deleted_counts_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    failure_code: Mapped[str | None] = mapped_column(String(120), nullable=True)
    failure_stage: Mapped[str | None] = mapped_column(String(120), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    purge_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    purge_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    restored_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    backup_delete_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_companion_deletion_idempotency"),
    )


class CompanionDeletionScopeRow(Base, UUIDMixin, TimestampMixin):
    """Transient row identifiers used to resume a multi-transaction purge."""

    __tablename__ = "companion_deletion_scope_rows"

    deletion_request_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companion_deletion_requests.id", ondelete="CASCADE"),
        nullable=False,
    )
    table_name: Mapped[str] = mapped_column(Text, nullable=False)
    row_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    __table_args__ = (
        UniqueConstraint(
            "deletion_request_id",
            "table_name",
            "row_id",
            name="uq_companion_deletion_scope_row",
        ),
    )


class ConversationDeletionProof(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    """Content-free evidence that one archived Conversation was erased."""

    __tablename__ = "conversation_deletion_proofs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    user_scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    companion_scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    conversation_scope_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    deleted_counts_json: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default="{}", nullable=False
    )
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


__all__ = [
    "CompanionDeletionRequest",
    "CompanionDeletionScopeRow",
    "ConversationDeletionProof",
]
