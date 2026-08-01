"""Companion and CompanionMode models."""

import uuid

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import UUIDMixin, TimestampMixin, SoftDeleteMixin, MetadataMixin, Base


class Companion(Base, UUIDMixin, TimestampMixin, SoftDeleteMixin, MetadataMixin):
    __tablename__ = "companions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(255), default="Echora")
    subtitle: Mapped[str | None] = mapped_column(
        String(500),
        default="A Persistent Companion Agent with Cognitive Memory",
        nullable=True,
    )
    identity_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_personality: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone_profile: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    companion_profile: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    current_mode: Mapped[str] = mapped_column(String(50), default="project")
    current_status: Mapped[str | None] = mapped_column(String(50), default="idle", nullable=True)
    current_focus: Mapped[str | None] = mapped_column(Text, nullable=True)
    companion_environment: Mapped[str] = mapped_column(String(20), default="product")
    provenance: Mapped[str] = mapped_column(String(30), default="user_created")

    modes = relationship("CompanionMode", back_populates="companion", lazy="selectin")


class CompanionMode(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_modes"

    companion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )

    mode_key: Mapped[str] = mapped_column(String(50), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    companion = relationship("Companion", back_populates="modes")

    __table_args__ = (
        UniqueConstraint("companion_id", "mode_key"),
    )
