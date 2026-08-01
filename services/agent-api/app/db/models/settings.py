"""BoundarySetting model."""

import uuid

from sqlalchemy import ARRAY, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import UUIDMixin, TimestampMixin, MetadataMixin, Base


class BoundarySetting(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "boundary_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    companion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False
    )

    memory_save_policy: Mapped[str] = mapped_column(String(50), default="review_important")
    sensitive_memory_policy: Mapped[str] = mapped_column(String(50), default="always_review")
    proactive_level: Mapped[str] = mapped_column(String(20), default="medium")
    notification_surface: Mapped[str] = mapped_column(String(50), default="hub_queue_only")

    allow_auto_memory_low_risk: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_proactive_presence: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_sensitive_memory_without_review: Mapped[bool] = mapped_column(Boolean, default=False)

    suppressed_presence_types: Mapped[list[str]] = mapped_column(
        ARRAY(String), default=list, server_default="{}"
    )
    boundary_rules: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")

    # ── Continuity: policy / presence / continuity ─────────────────────
    quiet_hours: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    suppressed_presence_rules: Mapped[dict] = mapped_column(JSONB, default=list, server_default="[]")
    memory_confirmation_policy: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    growth_confirmation_policy: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    feedback_usage_policy: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    continuity_visibility_policy: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    max_presence_per_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    min_presence_interval_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    meaningful_silence_enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    __table_args__ = (
        UniqueConstraint("user_id", "companion_id"),
    )
