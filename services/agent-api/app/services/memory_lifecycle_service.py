"""Create and list memory lifecycle events."""

import uuid
from typing import Any

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.memory_lifecycle_event import MemoryLifecycleEvent

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def create_memory_lifecycle_event(data: dict) -> dict:
    with get_session() as s:
        mle = create_memory_lifecycle_event_in_session(s, data)
        s.commit()
        s.refresh(mle)
        return _mle_dict(mle)


def _as_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def create_memory_lifecycle_event_in_session(
    session: Session,
    data: dict,
) -> MemoryLifecycleEvent:
    event = MemoryLifecycleEvent(
        user_id=_as_uuid(data["user_id"]),
        companion_id=_as_uuid(data["companion_id"]),
        conversation_id=_as_uuid(data.get("conversation_id")),
        message_id=_as_uuid(data.get("message_id")),
        trace_run_id=_as_uuid(data.get("trace_run_id")),
        memory_id=_as_uuid(data["memory_id"]),
        source_candidate_id=_as_uuid(data.get("source_candidate_id")),
        feedback_event_id=_as_uuid(data.get("feedback_event_id")),
        event_type=data["event_type"],
        title=data.get("title"),
        reason=data.get("reason"),
        previous_state=data.get("previous_state"),
        new_state=data.get("new_state"),
        previous_strength=data.get("previous_strength"),
        new_strength=data.get("new_strength"),
        strength_delta=data.get("strength_delta"),
        previous_confidence=data.get("previous_confidence"),
        new_confidence=data.get("new_confidence"),
        confidence_delta=data.get("confidence_delta"),
        previous_half_life_days=data.get("previous_half_life_days"),
        new_half_life_days=data.get("new_half_life_days"),
        score_json=data.get("score_json", {}),
        before_json=data.get("before_json", {}),
        after_json=data.get("after_json", {}),
        metadata_=data.get("metadata", {}),
    )
    session.add(event)
    session.flush()
    return event


def record_memory_change(
    session: Session,
    memory,
    *,
    event_type: str,
    reason: str,
    before: dict,
    after: dict,
    score_json: dict | None = None,
    feedback_event_id: uuid.UUID | None = None,
    trace_run_id: uuid.UUID | None = None,
) -> MemoryLifecycleEvent:
    return create_memory_lifecycle_event_in_session(
        session,
        {
            "user_id": memory.user_id,
            "companion_id": memory.companion_id,
            "conversation_id": memory.conversation_id,
            "trace_run_id": trace_run_id,
            "memory_id": memory.id,
            "feedback_event_id": feedback_event_id,
            "event_type": event_type,
            "title": event_type.replace("_", " ").title(),
            "reason": reason,
            "previous_state": before.get("state"),
            "new_state": after.get("state"),
            "previous_strength": before.get("memory_strength"),
            "new_strength": after.get("memory_strength"),
            "strength_delta": round(
                (after.get("memory_strength") or 0.0) - (before.get("memory_strength") or 0.0),
                6,
            ),
            "previous_confidence": before.get("confidence"),
            "new_confidence": after.get("confidence"),
            "confidence_delta": round(
                (after.get("confidence") or 0.0) - (before.get("confidence") or 0.0),
                6,
            ),
            "previous_half_life_days": before.get("half_life_days"),
            "new_half_life_days": after.get("half_life_days"),
            "score_json": score_json or {},
            "before_json": before,
            "after_json": after,
            "metadata": {"algorithm_version": "core-memory-lifecycle-v1"},
        },
    )


def list_memory_lifecycle_events(
    memory_id: uuid.UUID | None = None,
    event_type: str | None = None,
    page: int = 1, page_size: int = 20,
) -> dict:
    with get_session() as s:
        stmt = select(MemoryLifecycleEvent)
        if memory_id:
            stmt = stmt.where(MemoryLifecycleEvent.memory_id == memory_id)
        if event_type:
            stmt = stmt.where(MemoryLifecycleEvent.event_type == event_type)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(MemoryLifecycleEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = [_mle_dict(e) for e in s.execute(stmt).scalars().all()]
        return {"items": items, "total": total}


def list_lifecycle_events_for_memory(memory_id: uuid.UUID, page: int = 1, page_size: int = 20) -> dict:
    return list_memory_lifecycle_events(memory_id=memory_id, page=page, page_size=page_size)


def _mle_dict(e: MemoryLifecycleEvent) -> dict:
    return {
        "id": str(e.id),
        "user_id": str(e.user_id),
        "companion_id": str(e.companion_id),
        "conversation_id": str(e.conversation_id) if e.conversation_id else None,
        "message_id": str(e.message_id) if e.message_id else None,
        "trace_run_id": str(e.trace_run_id) if e.trace_run_id else None,
        "memory_id": str(e.memory_id),
        "source_candidate_id": str(e.source_candidate_id) if e.source_candidate_id else None,
        "feedback_event_id": str(e.feedback_event_id) if e.feedback_event_id else None,
        "event_type": e.event_type,
        "title": e.title,
        "reason": e.reason,
        "previous_state": e.previous_state,
        "new_state": e.new_state,
        "previous_strength": e.previous_strength,
        "new_strength": e.new_strength,
        "strength_delta": e.strength_delta,
        "previous_confidence": e.previous_confidence,
        "new_confidence": e.new_confidence,
        "confidence_delta": e.confidence_delta,
        "previous_half_life_days": e.previous_half_life_days,
        "new_half_life_days": e.new_half_life_days,
        "score_json": e.score_json,
        "before_json": e.before_json,
        "after_json": e.after_json,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }
