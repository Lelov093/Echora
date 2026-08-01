"""Companion companion memory / shared memory ORM models."""

import uuid

from sqlalchemy import Boolean, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class CompanionMemoryScope(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_memory_scopes"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    scope_type: Mapped[str] = mapped_column(Text, default="private_companion")
    scope_key: Mapped[str] = mapped_column(Text, default="default")
    title: Mapped[str] = mapped_column(Text, default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope_status: Mapped[str] = mapped_column(Text, default="active")
    default_write_policy: Mapped[str] = mapped_column(Text, default="private_only")
    visibility_policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class CompanionPrivateMemoryLink(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_private_memory_links"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id"), nullable=False)
    memory_scope_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companion_memory_scopes.id"), nullable=False)
    link_status: Mapped[str] = mapped_column(Text, default="active")


class RelationshipMemoryLink(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "relationship_memory_links"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    related_companion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True
    )
    memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id"), nullable=False)
    relationship_contract_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companion_relationship_contracts.id"), nullable=False
    )
    link_status: Mapped[str] = mapped_column(Text, default="active")


class SharedEpisodicMemory(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "shared_episodic_memories"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(Text, default="active")
    source_type: Mapped[str] = mapped_column(Text, default="candidate_review")
    visibility_policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    scene_context_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class SharedMemoryCandidate(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "shared_memory_candidates"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    source_memory_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memory_candidates.id"), nullable=True
    )
    source_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("memories.id"), nullable=True
    )
    proposed_shared_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_episodic_memories.id"), nullable=True
    )
    source_shared_experience_record_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_experience_records.id"), nullable=True
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    content: Mapped[str] = mapped_column(Text, default="")
    candidate_status: Mapped[str] = mapped_column(Text, default="pending_review")
    requires_user_review: Mapped[bool] = mapped_column(Boolean, default=True)
    candidate_policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class SharedMemoryParticipant(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "shared_memory_participants"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    shared_memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_episodic_memories.id"), nullable=False
    )
    participant_type: Mapped[str] = mapped_column(Text, nullable=False)
    participant_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    participant_companion_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True
    )
    participant_role: Mapped[str] = mapped_column(Text, default="active")
    private_memory_sync_policy: Mapped[str] = mapped_column(Text, default="review_required")


class CrossCompanionMemoryEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "cross_companion_memory_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    source_companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    target_companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    memory_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id"), nullable=True)
    shared_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_episodic_memories.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, default="pending_review")
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class CrossCompanionMemoryReview(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "cross_companion_memory_reviews"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    cross_companion_memory_event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("cross_companion_memory_events.id"), nullable=False
    )
    decision: Mapped[str] = mapped_column(Text, default="pending")
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    approved_policy_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class PrivateToSharedMemoryReview(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "private_to_shared_memory_reviews"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    source_companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    memory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id"), nullable=False)
    shared_memory_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_memory_candidates.id"), nullable=True
    )
    target_shared_memory_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_episodic_memories.id"), nullable=True
    )
    decision: Mapped[str] = mapped_column(Text, default="pending")
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class SharedToPrivateMemoryReview(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "shared_to_private_memory_reviews"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    target_companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    shared_memory_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("shared_episodic_memories.id"), nullable=False
    )
    target_memory_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id"), nullable=True)
    decision: Mapped[str] = mapped_column(Text, default="pending")
    review_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


__all__ = [
    "CompanionMemoryScope",
    "CompanionPrivateMemoryLink",
    "RelationshipMemoryLink",
    "SharedEpisodicMemory",
    "SharedMemoryCandidate",
    "SharedMemoryParticipant",
    "CrossCompanionMemoryEvent",
    "CrossCompanionMemoryReview",
    "PrivateToSharedMemoryReview",
    "SharedToPrivateMemoryReview",
]
