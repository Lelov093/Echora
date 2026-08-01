"""MemoryEdge model — reserved for Companion memory graph."""

import uuid

from sqlalchemy import Double, ForeignKey, String, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDMixin, TimestampMixin, MetadataMixin, Base


class MemoryEdge(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "memory_edges"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )

    source_memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id"), nullable=False
    )
    target_memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id"), nullable=False
    )
    edge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    edge_weight: Mapped[float] = mapped_column(Double, default=0.5)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    edge_source: Mapped[str] = mapped_column(Text, default="manual")
    confidence: Mapped[float] = mapped_column(Double, default=0.5)

    __table_args__ = (
        CheckConstraint("edge_weight BETWEEN 0 AND 1", name="ck_memory_edges_weight"),
        CheckConstraint(
            "confidence BETWEEN 0 AND 1",
            name="ck_memory_edges_confidence",
        ),
        CheckConstraint(
            "source_memory_id <> target_memory_id", name="ck_memory_edges_no_self"
        ),
    )
