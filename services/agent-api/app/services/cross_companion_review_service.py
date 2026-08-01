"""Companion cross-companion memory review service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    CrossCompanionMemoryEvent,
    CrossCompanionMemoryReview,
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


def list_cross_companion_memory_reviews(
    decision: str | None = None, page: int = 1, page_size: int = 20
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(CrossCompanionMemoryReview)
        if decision:
            stmt = stmt.where(CrossCompanionMemoryReview.decision == decision)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(CrossCompanionMemoryReview.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def create_cross_companion_memory_review(user_id: uuid.UUID, payload: dict[str, Any]) -> CrossCompanionMemoryReview | None:
    with get_session() as s:
        event = None
        if payload.get("cross_companion_memory_event_id"):
            event = s.get(CrossCompanionMemoryEvent, _to_uuid(payload["cross_companion_memory_event_id"]))
        if event is None:
            event = CrossCompanionMemoryEvent(
                user_id=user_id,
                source_companion_id=_to_uuid(payload["source_companion_id"]),
                target_companion_id=_to_uuid(payload["target_companion_id"]),
                memory_id=_to_uuid(payload.get("memory_id")),
                shared_memory_id=_to_uuid(payload.get("shared_memory_id")),
                event_type=payload.get("event_type", "share_request"),
                status="pending_review",
                reason=payload.get("reason"),
                review_required=True,
                policy_json=payload.get("policy_json") or {},
                metadata_={"implementation_origin": "shared_memory", **(payload.get("metadata") or {})},
            )
            s.add(event)
            s.flush()
        review = CrossCompanionMemoryReview(
            user_id=user_id,
            cross_companion_memory_event_id=event.id,
            decision=payload.get("decision", "pending"),
            review_reason=payload.get("review_reason"),
            approved_policy_json=payload.get("approved_policy_json") or {},
            metadata_={"implementation_origin": "shared_memory", **(payload.get("metadata") or {})},
        )
        s.add(review)
        s.commit()
        s.refresh(review)
        return review


def decide_cross_companion_memory_review(review_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        review = s.get(CrossCompanionMemoryReview, review_id)
        if not review:
            return None
        event = s.get(CrossCompanionMemoryEvent, review.cross_companion_memory_event_id)
        if not event:
            return None

        review.decision = payload.get("decision", review.decision)
        review.review_reason = payload.get("review_reason", review.review_reason)
        review.approved_policy_json = payload.get("approved_policy_json") or review.approved_policy_json or {}
        review.updated_at = datetime.now(timezone.utc)

        if review.decision == "approved":
            event.status = "approved"
            if event.shared_memory_id and payload.get("create_shared_to_private_review", False):
                existing = s.execute(
                    select(SharedToPrivateMemoryReview).where(
                        SharedToPrivateMemoryReview.shared_memory_id == event.shared_memory_id,
                        SharedToPrivateMemoryReview.target_companion_id == event.target_companion_id,
                        SharedToPrivateMemoryReview.decision == "pending",
                    )
                ).scalar_one_or_none()
                if existing is None:
                    s.add(
                        SharedToPrivateMemoryReview(
                            user_id=event.user_id,
                            target_companion_id=event.target_companion_id,
                            shared_memory_id=event.shared_memory_id,
                            decision="pending",
                            review_reason="Pending explicit approval after cross-companion review.",
                            metadata_={"implementation_origin": "shared_memory", "source": "cross_companion_review"},
                        )
                    )
        elif review.decision == "rejected":
            event.status = "rejected"
        else:
            event.status = "recorded"
        event.updated_at = datetime.now(timezone.utc)

        s.commit()
        s.refresh(review)
        s.refresh(event)
        return {"review": _cross_review_dict(review), "event": _cross_event_dict(event)}


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _cross_event_dict(event: CrossCompanionMemoryEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "user_id": str(event.user_id),
        "source_companion_id": str(event.source_companion_id),
        "target_companion_id": str(event.target_companion_id),
        "memory_id": str(event.memory_id) if event.memory_id else None,
        "shared_memory_id": str(event.shared_memory_id) if event.shared_memory_id else None,
        "event_type": event.event_type,
        "status": event.status,
        "reason": event.reason,
        "review_required": event.review_required,
        "policy_json": event.policy_json or {},
        "created_at": event.created_at.isoformat() if event.created_at else None,
        "updated_at": event.updated_at.isoformat() if event.updated_at else None,
    }


def _cross_review_dict(review: CrossCompanionMemoryReview) -> dict[str, Any]:
    return {
        "id": str(review.id),
        "user_id": str(review.user_id),
        "cross_companion_memory_event_id": str(review.cross_companion_memory_event_id),
        "decision": review.decision,
        "review_reason": review.review_reason,
        "approved_policy_json": review.approved_policy_json or {},
        "created_at": review.created_at.isoformat() if review.created_at else None,
        "updated_at": review.updated_at.isoformat() if review.updated_at else None,
    }
