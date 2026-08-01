"""ProjectContext and CreativeContext models."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDMixin, TimestampMixin, MetadataMixin, Base


class ProjectContext(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "project_contexts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_phase: Mapped[str | None] = mapped_column(String(200), nullable=True)
    current_goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    principles: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    constraints: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    decisions: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    next_steps: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class CreativeContext(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "creative_contexts"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    creative_domain: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tone_preferences: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    style_preferences: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    canon_notes: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    character_notes: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    worldbuilding_notes: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
