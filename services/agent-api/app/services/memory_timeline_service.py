"""Aggregate memory lifecycle and usage events into a unified timeline."""

import uuid

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.memory_usage_event import MemoryUsageEvent
from app.db.models.memory_lifecycle_event import MemoryLifecycleEvent
from app.db.models.memory import Memory

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def _build_usage_item(e: MemoryUsageEvent, memory_summary_map: dict) -> dict:
    summary = memory_summary_map.get(e.memory_id, None)
    return {
        "source": "usage",
        "event_type": e.event_type,
        "event_id": str(e.id),
        "memory_id": str(e.memory_id),
        "memory_summary": summary,
        "title": e.event_type,
        "reason": e.why_selected,
        "used_in_response": e.used_in_response,
        "used_in_growth": e.used_in_growth,
        "used_in_presence": e.used_in_presence,
        "used_in_relationship": e.used_in_relationship,
        "retrieval_score": e.retrieval_score,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def _build_lifecycle_item(e: MemoryLifecycleEvent, memory_summary_map: dict) -> dict:
    summary = memory_summary_map.get(e.memory_id, None)
    return {
        "source": "lifecycle",
        "event_type": e.event_type,
        "event_id": str(e.id),
        "memory_id": str(e.memory_id),
        "memory_summary": summary,
        "title": e.title,
        "reason": e.reason,
        "previous_state": e.previous_state,
        "new_state": e.new_state,
        "strength_delta": e.strength_delta,
        "confidence_delta": e.confidence_delta,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


def _resolve_memory_summaries(s: Session, memory_ids: set) -> dict:
    """Return a mapping of memory_id -> summary for the given set of memory IDs."""
    if not memory_ids:
        return {}
    stmt = select(Memory.id, Memory.summary).where(Memory.id.in_(memory_ids))
    rows = s.execute(stmt).all()
    return {row[0]: row[1] for row in rows}


def get_memory_timeline(
    companion_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    page: int = 1, page_size: int = 50,
) -> dict:
    with get_session() as s:
        # Collect all events
        usage_stmt = select(MemoryUsageEvent)
        lifecycle_stmt = select(MemoryLifecycleEvent)

        if companion_id:
            usage_stmt = usage_stmt.where(MemoryUsageEvent.companion_id == companion_id)
            lifecycle_stmt = lifecycle_stmt.where(MemoryLifecycleEvent.companion_id == companion_id)
        if user_id:
            usage_stmt = usage_stmt.where(MemoryUsageEvent.user_id == user_id)
            lifecycle_stmt = lifecycle_stmt.where(MemoryLifecycleEvent.user_id == user_id)

        usage_events = s.execute(usage_stmt).scalars().all()
        lifecycle_events = s.execute(lifecycle_stmt).scalars().all()

        # Resolve memory summaries
        memory_ids = set()
        for e in usage_events:
            memory_ids.add(e.memory_id)
        for e in lifecycle_events:
            memory_ids.add(e.memory_id)
        summary_map = _resolve_memory_summaries(s, memory_ids)

        # Build unified items
        items = []
        for e in usage_events:
            items.append(_build_usage_item(e, summary_map))
        for e in lifecycle_events:
            items.append(_build_lifecycle_item(e, summary_map))

        # Sort by created_at DESC
        items.sort(key=lambda x: x["created_at"] or "", reverse=True)

        total = len(items)
        # Apply pagination
        start = (page - 1) * page_size
        end = start + page_size
        items = items[start:end]

        return {"items": items, "total": total}


def get_single_memory_timeline(
    memory_id: uuid.UUID,
    page: int = 1, page_size: int = 50,
) -> dict:
    with get_session() as s:
        usage_events = s.execute(
            select(MemoryUsageEvent).where(MemoryUsageEvent.memory_id == memory_id)
            .order_by(MemoryUsageEvent.created_at.desc())
        ).scalars().all()

        lifecycle_events = s.execute(
            select(MemoryLifecycleEvent).where(MemoryLifecycleEvent.memory_id == memory_id)
            .order_by(MemoryLifecycleEvent.created_at.desc())
        ).scalars().all()

        # Resolve memory summary
        mem = s.get(Memory, memory_id)
        summary = mem.summary if mem else None

        items = []
        for e in usage_events:
            items.append(_build_usage_item(e, {memory_id: summary}))
        for e in lifecycle_events:
            items.append(_build_lifecycle_item(e, {memory_id: summary}))

        # Sort by created_at DESC
        items.sort(key=lambda x: x["created_at"] or "", reverse=True)

        total = len(items)
        start = (page - 1) * page_size
        end = start + page_size
        items = items[start:end]

        return {"items": items, "total": total}
