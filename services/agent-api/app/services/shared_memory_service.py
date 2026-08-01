"""Companion shared memory and review service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    Companion,
    Memory,
    PrivateToSharedMemoryReview,
    SharedEpisodicMemory,
    SharedMemoryCandidate,
    SharedMemoryParticipant,
    SharedToPrivateMemoryReview,
)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def list_shared_episodic_memories(
    status: str | None = None, page: int = 1, page_size: int = 20
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(SharedEpisodicMemory)
        if status:
            stmt = stmt.where(SharedEpisodicMemory.status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(SharedEpisodicMemory.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def create_shared_episodic_memory(user_id: uuid.UUID, payload: dict[str, Any]) -> SharedEpisodicMemory:
    with get_session() as s:
        shared = SharedEpisodicMemory(
            user_id=user_id,
            title=payload.get("title"),
            summary=payload.get("summary", ""),
            content=payload.get("content", ""),
            status=payload.get("status", "active"),
            source_type=payload.get("source_type", "manual"),
            visibility_policy_json=payload.get("visibility_policy_json") or {},
            scene_context_json=payload.get("scene_context_json") or {},
            metadata_={"implementation_origin": "shared_memory", **(payload.get("metadata") or {})},
        )
        s.add(shared)
        s.flush()

        for participant in payload.get("participants", []):
            s.add(
                SharedMemoryParticipant(
                    user_id=user_id,
                    shared_memory_id=shared.id,
                    participant_type=participant["participant_type"],
                    participant_user_id=_to_uuid(participant.get("participant_user_id")),
                    participant_companion_id=_to_uuid(participant.get("participant_companion_id")),
                    participant_role=participant.get("participant_role", "active"),
                    private_memory_sync_policy=participant.get("private_memory_sync_policy", "review_required"),
                    metadata_={"implementation_origin": "shared_memory"},
                )
            )

        for target_companion_id in payload.get("private_sync_targets", []):
            s.add(
                SharedToPrivateMemoryReview(
                    user_id=user_id,
                    target_companion_id=_to_uuid(target_companion_id),
                    shared_memory_id=shared.id,
                    decision="pending",
                    review_reason="Pending explicit user approval for shared-to-private sync.",
                    metadata_={"implementation_origin": "shared_memory", "source": "shared_memory_create"},
                )
            )

        s.commit()
        s.refresh(shared)
        return shared


def list_shared_memory_candidates(
    status: str | None = None, page: int = 1, page_size: int = 20
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(SharedMemoryCandidate)
        if status:
            stmt = stmt.where(SharedMemoryCandidate.candidate_status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(SharedMemoryCandidate.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def create_shared_memory_candidate(user_id: uuid.UUID, payload: dict[str, Any]) -> SharedMemoryCandidate:
    with get_session() as s:
        source_memory_id = _to_uuid(payload.get("source_memory_id"))
        candidate = SharedMemoryCandidate(
            user_id=user_id,
            source_memory_candidate_id=_to_uuid(payload.get("source_memory_candidate_id")),
            source_memory_id=source_memory_id,
            source_shared_experience_record_id=_to_uuid(payload.get("source_shared_experience_record_id")),
            title=payload.get("title"),
            summary=payload.get("summary", ""),
            content=payload.get("content", ""),
            candidate_status=payload.get("candidate_status", "pending_review"),
            requires_user_review=payload.get("requires_user_review", True),
            candidate_policy_json=payload.get("candidate_policy_json") or {},
            metadata_={"implementation_origin": "shared_memory", **(payload.get("metadata") or {})},
        )
        s.add(candidate)
        s.flush()

        if source_memory_id:
            source_memory = s.get(Memory, source_memory_id)
            if source_memory:
                s.add(
                    PrivateToSharedMemoryReview(
                        user_id=user_id,
                        source_companion_id=source_memory.owner_companion_id or source_memory.companion_id,
                        memory_id=source_memory.id,
                        shared_memory_candidate_id=candidate.id,
                        decision="pending",
                        review_reason="Pending explicit review for private-to-shared promotion.",
                        metadata_={"implementation_origin": "shared_memory", "source": "shared_memory_candidate_create"},
                    )
                )
        s.commit()
        s.refresh(candidate)
        return candidate


def decide_shared_memory_candidate(candidate_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        candidate = s.get(SharedMemoryCandidate, candidate_id)
        if not candidate:
            return None

        decision = payload.get("decision", "").lower()
        if decision not in {"approved", "rejected", "merged"}:
            return None

        if decision == "approved" and candidate.source_memory_id:
            review = s.execute(
                select(PrivateToSharedMemoryReview).where(
                    PrivateToSharedMemoryReview.shared_memory_candidate_id == candidate.id,
                    PrivateToSharedMemoryReview.decision == "approved",
                )
            ).scalar_one_or_none()
            if review is None:
                return {"error": "PRIVATE_TO_SHARED_REVIEW_REQUIRED"}

        if decision == "approved":
            shared = s.get(SharedEpisodicMemory, candidate.proposed_shared_memory_id) if candidate.proposed_shared_memory_id else None
            if shared is None:
                shared = SharedEpisodicMemory(
                    user_id=candidate.user_id,
                    title=payload.get("title", candidate.title),
                    summary=payload.get("summary", candidate.summary),
                    content=payload.get("content", candidate.content),
                    status="active",
                    source_type="review_approved",
                    visibility_policy_json=payload.get("visibility_policy_json") or {},
                    scene_context_json=payload.get("scene_context_json") or {},
                    metadata_={"implementation_origin": "shared_memory", "source_candidate_id": str(candidate.id)},
                )
                s.add(shared)
                s.flush()
                _bootstrap_shared_participants(s, candidate, shared)
            candidate.proposed_shared_memory_id = shared.id
            candidate.candidate_status = "approved"
        elif decision == "rejected":
            candidate.candidate_status = "rejected"
        else:
            candidate.candidate_status = "merged"

        candidate.updated_at = datetime.now(timezone.utc)
        if payload.get("review_reason"):
            candidate.metadata_ = {
                **(candidate.metadata_ or {}),
                "decision_reason": payload["review_reason"],
            }
        s.commit()
        s.refresh(candidate)
        return {
            "candidate": _shared_candidate_dict(candidate),
            "shared_memory": _shared_memory_dict(s.get(SharedEpisodicMemory, candidate.proposed_shared_memory_id))
            if candidate.proposed_shared_memory_id
            else None,
        }


def list_private_to_shared_reviews(
    decision: str | None = None, page: int = 1, page_size: int = 20
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(PrivateToSharedMemoryReview)
        if decision:
            stmt = stmt.where(PrivateToSharedMemoryReview.decision == decision)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(PrivateToSharedMemoryReview.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def decide_private_to_shared_review(review_id: uuid.UUID, payload: dict[str, Any]) -> PrivateToSharedMemoryReview | None:
    with get_session() as s:
        review = s.get(PrivateToSharedMemoryReview, review_id)
        if not review:
            return None
        review.decision = payload.get("decision", review.decision)
        review.review_reason = payload.get("review_reason", review.review_reason)
        if payload.get("target_shared_memory_id"):
            review.target_shared_memory_id = _to_uuid(payload["target_shared_memory_id"])
        review.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(review)
        return review


def list_shared_to_private_reviews(
    decision: str | None = None, page: int = 1, page_size: int = 20
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(SharedToPrivateMemoryReview)
        if decision:
            stmt = stmt.where(SharedToPrivateMemoryReview.decision == decision)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(SharedToPrivateMemoryReview.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def decide_shared_to_private_review(review_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    from app.services import memory_service

    prepared = None
    with get_session() as read_session:
        source_review = read_session.get(SharedToPrivateMemoryReview, review_id)
        if source_review and payload.get("decision", source_review.decision) == "approved" and source_review.target_memory_id is None:
            source_shared = read_session.get(SharedEpisodicMemory, source_review.shared_memory_id)
            if source_shared:
                prepared = memory_service.prepare_saved_memory_content(payload.get("content", source_shared.content))

    with get_session() as s:
        review = s.get(SharedToPrivateMemoryReview, review_id)
        if not review:
            return None

        review.decision = payload.get("decision", review.decision)
        review.review_reason = payload.get("review_reason", review.review_reason)
        created_memory = None
        if review.decision == "approved" and review.target_memory_id is None:
            shared = s.get(SharedEpisodicMemory, review.shared_memory_id)
            companion = s.get(Companion, review.target_companion_id)
            if shared and companion and prepared:
                created_memory = Memory(
                    user_id=review.user_id,
                    companion_id=companion.id,
                    owner_companion_id=companion.id,
                    shared_memory_id=shared.id,
                    memory_scope_type="private_companion",
                    memory_layer="shared_episodic",
                    visibility_policy_json=shared.visibility_policy_json or {},
                    type=payload.get("memory_type", "episodic"),
                    state="active",
                    visibility="user_visible",
                    consent_status="user_confirmed",
                    content=prepared["content"],
                    summary=payload.get("summary", shared.summary),
                    source_message_ids=[],
                    source_modality="text",
                    importance=0.7,
                    confidence=0.8,
                    emotional_intensity=0.0,
                    goal_relevance=0.0,
                    relationship_impact=0.0,
                    correction_value=0.0,
                    memory_strength=0.7,
                    decay_rate=0.01,
                    reactivation_count=0,
                    positive_confirmations=1,
                    correction_count=0,
                    accepted_count=1,
                    rejected_count=0,
                    usage_feedback={},
                    helpful_feedback={},
                    mode_specific_feedback={},
                    feedback_score=0.0,
                    helpful_count=0,
                    irrelevant_count=0,
                    outdated_count=0,
                    wrong_count=0,
                    impact_summary={},
                    lifecycle_summary={},
                    abstraction_level=0,
                    metadata_={"implementation_origin": "shared_memory", "source_shared_memory_id": str(shared.id)},
                )
                memory_service.initialize_saved_memory_in_session(
                    s, created_memory, prepared,
                    reason=payload.get("review_reason") or "approved_shared_to_private_memory",
                )
                review.target_memory_id = created_memory.id
        review.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(review)
        if created_memory is not None:
            s.refresh(created_memory)
        return {
            "review": _shared_to_private_review_dict(review),
            "memory": _memory_copy_dict(created_memory) if created_memory else None,
        }


def _bootstrap_shared_participants(s: Session, candidate: SharedMemoryCandidate, shared: SharedEpisodicMemory) -> None:
    existing_owner = s.execute(
        select(SharedMemoryParticipant).where(
            SharedMemoryParticipant.shared_memory_id == shared.id,
            SharedMemoryParticipant.participant_type == "user",
            SharedMemoryParticipant.participant_user_id == candidate.user_id,
        )
    ).scalar_one_or_none()
    if existing_owner is None:
        s.add(
            SharedMemoryParticipant(
                user_id=candidate.user_id,
                shared_memory_id=shared.id,
                participant_type="user",
                participant_user_id=candidate.user_id,
                participant_role="owner",
                private_memory_sync_policy="none",
                metadata_={"implementation_origin": "shared_memory"},
            )
        )
    if candidate.source_memory_id:
        memory = s.get(Memory, candidate.source_memory_id)
        if memory:
            existing_companion = s.execute(
                select(SharedMemoryParticipant).where(
                    SharedMemoryParticipant.shared_memory_id == shared.id,
                    SharedMemoryParticipant.participant_type == "companion",
                    SharedMemoryParticipant.participant_companion_id == memory.owner_companion_id,
                )
            ).scalar_one_or_none()
            if existing_companion is None:
                s.add(
                    SharedMemoryParticipant(
                        user_id=candidate.user_id,
                        shared_memory_id=shared.id,
                        participant_type="companion",
                        participant_companion_id=memory.owner_companion_id,
                        participant_role="active",
                        private_memory_sync_policy="review_required",
                        metadata_={"implementation_origin": "shared_memory"},
                    )
                )


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _shared_memory_dict(shared: SharedEpisodicMemory | None) -> dict[str, Any] | None:
    if shared is None:
        return None
    return {
        "id": str(shared.id),
        "user_id": str(shared.user_id),
        "title": shared.title,
        "summary": shared.summary,
        "content": shared.content,
        "status": shared.status,
        "source_type": shared.source_type,
        "visibility_policy_json": shared.visibility_policy_json or {},
        "scene_context_json": shared.scene_context_json or {},
        "created_at": shared.created_at.isoformat() if shared.created_at else None,
        "updated_at": shared.updated_at.isoformat() if shared.updated_at else None,
    }


def _shared_candidate_dict(candidate: SharedMemoryCandidate) -> dict[str, Any]:
    return {
        "id": str(candidate.id),
        "user_id": str(candidate.user_id),
        "source_memory_candidate_id": str(candidate.source_memory_candidate_id) if candidate.source_memory_candidate_id else None,
        "source_memory_id": str(candidate.source_memory_id) if candidate.source_memory_id else None,
        "proposed_shared_memory_id": str(candidate.proposed_shared_memory_id) if candidate.proposed_shared_memory_id else None,
        "source_shared_experience_record_id": str(candidate.source_shared_experience_record_id) if candidate.source_shared_experience_record_id else None,
        "title": candidate.title,
        "summary": candidate.summary,
        "content": candidate.content,
        "candidate_status": candidate.candidate_status,
        "requires_user_review": candidate.requires_user_review,
        "candidate_policy_json": candidate.candidate_policy_json or {},
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
        "updated_at": candidate.updated_at.isoformat() if candidate.updated_at else None,
    }


def _private_to_shared_review_dict(review: PrivateToSharedMemoryReview) -> dict[str, Any]:
    return {
        "id": str(review.id),
        "user_id": str(review.user_id),
        "source_companion_id": str(review.source_companion_id),
        "memory_id": str(review.memory_id),
        "shared_memory_candidate_id": str(review.shared_memory_candidate_id) if review.shared_memory_candidate_id else None,
        "target_shared_memory_id": str(review.target_shared_memory_id) if review.target_shared_memory_id else None,
        "decision": review.decision,
        "review_reason": review.review_reason,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "updated_at": review.updated_at.isoformat() if review.updated_at else None,
    }


def _shared_to_private_review_dict(review: SharedToPrivateMemoryReview) -> dict[str, Any]:
    return {
        "id": str(review.id),
        "user_id": str(review.user_id),
        "target_companion_id": str(review.target_companion_id),
        "shared_memory_id": str(review.shared_memory_id),
        "target_memory_id": str(review.target_memory_id) if review.target_memory_id else None,
        "decision": review.decision,
        "review_reason": review.review_reason,
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "updated_at": review.updated_at.isoformat() if review.updated_at else None,
    }


def _memory_copy_dict(memory: Memory | None) -> dict[str, Any] | None:
    if memory is None:
        return None
    return {
        "id": str(memory.id),
        "owner_companion_id": str(memory.owner_companion_id) if memory.owner_companion_id else None,
        "shared_memory_id": str(memory.shared_memory_id) if memory.shared_memory_id else None,
        "memory_scope_type": memory.memory_scope_type,
        "memory_layer": memory.memory_layer,
        "type": memory.type,
        "summary": memory.summary,
        "content": memory.content,
    }
