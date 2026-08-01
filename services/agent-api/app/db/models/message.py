"""Message model."""

import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import UUIDMixin, TimestampMixin, SoftDeleteMixin, MetadataMixin, Base


class Message(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, MetadataMixin):
    __tablename__ = "messages"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False
    )

    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_format: Mapped[str] = mapped_column(String(20), default="text")
    source_modality: Mapped[str] = mapped_column(String(20), default="text")

    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    model_provider: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    conversation = relationship("Conversation", back_populates="messages")
