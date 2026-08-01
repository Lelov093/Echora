"""Companion companion identity / persona / contract / boundary ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class CompanionIdentityProfile(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_identity_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    identity_summary: Mapped[str] = mapped_column(Text, default="")
    origin_story: Mapped[str | None] = mapped_column(Text, nullable=True)
    self_continuity_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    core_traits_json: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    identity_labels_json: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    voice_style_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    avatar_style_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    profile_status: Mapped[str] = mapped_column(Text, default="active")


class CompanionPersonaProfile(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_persona_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    persona_summary: Mapped[str] = mapped_column(Text, default="")
    communication_style_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone_descriptors_json: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    core_values_json: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    response_preferences_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    persona_lock_level: Mapped[str] = mapped_column(Text, default="guarded")
    drift_guard_level: Mapped[str] = mapped_column(Text, default="standard")
    presence_style: Mapped[str] = mapped_column(Text, default="balanced")


class CompanionRelationshipContract(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_relationship_contracts"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    relationship_role: Mapped[str] = mapped_column(Text, default="companion")
    contract_status: Mapped[str] = mapped_column(Text, default="active")
    contract_summary: Mapped[str] = mapped_column(Text, default="")
    collaboration_style_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    support_scope_json: Mapped[list] = mapped_column(JSONB, default=list, server_default="[]")
    shared_memory_policy: Mapped[str] = mapped_column(Text, default="candidate_review")
    cross_companion_disclosure_policy: Mapped[str] = mapped_column(Text, default="review_required")
    contract_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class CompanionBoundaryProfile(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_boundary_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    boundary_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    private_memory_default: Mapped[str] = mapped_column(Text, default="private_companion_only")
    shared_memory_default: Mapped[str] = mapped_column(Text, default="candidate_review")
    global_memory_read_scope: Mapped[str] = mapped_column(Text, default="low_risk_summary_only")
    cross_companion_read_policy: Mapped[str] = mapped_column(Text, default="blocked")
    review_required_private_to_shared: Mapped[bool] = mapped_column(Boolean, default=True)
    review_required_shared_to_private: Mapped[bool] = mapped_column(Boolean, default=True)
    review_required_cross_companion_share: Mapped[bool] = mapped_column(Boolean, default=True)
    presence_interrupt_policy: Mapped[str] = mapped_column(Text, default="respect_existing_boundary")


class CompanionVisibilityPolicy(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_visibility_policies"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    memory_visibility_policy: Mapped[str] = mapped_column(Text, default="scoped_summary")
    user_global_memory_scope: Mapped[str] = mapped_column(Text, default="low_risk_summary_only")
    relationship_memory_scope: Mapped[str] = mapped_column(Text, default="contract_scoped")
    allow_low_risk_summary_read: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_authorized_global_read: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_sensitive_global_read: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_other_companion_private_read: Mapped[bool] = mapped_column(Boolean, default=False)
    visibility_rules_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class CompanionLifecycleEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_lifecycle_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_source: Mapped[str] = mapped_column(Text, default="migration")
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    previous_state_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    new_state_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    review_required: Mapped[bool] = mapped_column(Boolean, default=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


__all__ = [
    "CompanionIdentityProfile",
    "CompanionPersonaProfile",
    "CompanionRelationshipContract",
    "CompanionBoundaryProfile",
    "CompanionVisibilityPolicy",
    "CompanionLifecycleEvent",
]
