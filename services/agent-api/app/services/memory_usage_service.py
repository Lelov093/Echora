"""Create and list memory usage events."""

import uuid

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.memory import Memory
from app.db.models.memory_usage_event import MemoryUsageEvent

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def create_memory_usage_event(data: dict) -> dict:
    with get_session() as s:
        memory_id = uuid.UUID(data["memory_id"])
        companion_id = uuid.UUID(data["companion_id"])

        memory = s.get(Memory, memory_id)
        if (
            memory is None
            or memory.companion_id != companion_id
            or memory.owner_companion_id != companion_id
        ):
            raise ValueError("Memory usage event violates companion ownership boundary")
        mue = MemoryUsageEvent(
            user_id=uuid.UUID(data["user_id"]),
            companion_id=companion_id,
            conversation_id=uuid.UUID(data["conversation_id"]) if data.get("conversation_id") else None,
            message_id=uuid.UUID(data["message_id"]) if data.get("message_id") else None,
            trace_run_id=uuid.UUID(data["trace_run_id"]) if data.get("trace_run_id") else None,
            trace_step_id=uuid.UUID(data["trace_step_id"]) if data.get("trace_step_id") else None,
            memory_id=memory_id,
            event_type=data["event_type"],
            semantic_similarity=data.get("semantic_similarity"),
            retrieval_score=data.get("retrieval_score"),
            memory_strength_snapshot=data.get("memory_strength_snapshot"),
            confidence_snapshot=data.get("confidence_snapshot"),
            goal_relevance_snapshot=data.get("goal_relevance_snapshot"),
            relationship_impact_snapshot=data.get("relationship_impact_snapshot"),
            rank_before_rerank=data.get("rank_before_rerank"),
            rank_after_rerank=data.get("rank_after_rerank"),
            selected_for_context=data.get("selected_for_context", False),
            used_in_response=data.get("used_in_response", False),
            used_in_growth=data.get("used_in_growth", False),
            used_in_presence=data.get("used_in_presence", False),
            used_in_relationship=data.get("used_in_relationship", False),
            why_selected=data.get("why_selected"),
            why_excluded=data.get("why_excluded"),
            feedback_event_id=uuid.UUID(data["feedback_event_id"]) if data.get("feedback_event_id") else None,
            feedback_label=data.get("feedback_label"),
            score_json=data.get("score_json", {}),
            usage_context=data.get("usage_context", {}),
        )
        s.add(mue)
        s.commit()
        return _mue_dict(mue)


def list_memory_usage_events(
    memory_id: uuid.UUID | None = None,
    event_type: str | None = None,
    trace_run_id: uuid.UUID | None = None,
    page: int = 1, page_size: int = 20,
) -> dict:
    with get_session() as s:
        stmt = select(MemoryUsageEvent)
        if memory_id:
            stmt = stmt.where(MemoryUsageEvent.memory_id == memory_id)
        if event_type:
            stmt = stmt.where(MemoryUsageEvent.event_type == event_type)
        if trace_run_id:
            stmt = stmt.where(MemoryUsageEvent.trace_run_id == trace_run_id)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(MemoryUsageEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = [_mue_dict(e) for e in s.execute(stmt).scalars().all()]
        return {"items": items, "total": total}


def list_usage_events_for_memory(memory_id: uuid.UUID, page: int = 1, page_size: int = 20) -> dict:
    return list_memory_usage_events(memory_id=memory_id, page=page, page_size=page_size)


def _mue_dict(e: MemoryUsageEvent) -> dict:
    return {
        "id": str(e.id),
        "user_id": str(e.user_id),
        "companion_id": str(e.companion_id),
        "conversation_id": str(e.conversation_id) if e.conversation_id else None,
        "message_id": str(e.message_id) if e.message_id else None,
        "trace_run_id": str(e.trace_run_id) if e.trace_run_id else None,
        "trace_step_id": str(e.trace_step_id) if e.trace_step_id else None,
        "memory_id": str(e.memory_id),
        "event_type": e.event_type,
        "semantic_similarity": e.semantic_similarity,
        "retrieval_score": e.retrieval_score,
        "memory_strength_snapshot": e.memory_strength_snapshot,
        "confidence_snapshot": e.confidence_snapshot,
        "goal_relevance_snapshot": e.goal_relevance_snapshot,
        "relationship_impact_snapshot": e.relationship_impact_snapshot,
        "rank_before_rerank": e.rank_before_rerank,
        "rank_after_rerank": e.rank_after_rerank,
        "selected_for_context": e.selected_for_context,
        "used_in_response": e.used_in_response,
        "used_in_growth": e.used_in_growth,
        "used_in_presence": e.used_in_presence,
        "used_in_relationship": e.used_in_relationship,
        "why_selected": e.why_selected,
        "why_excluded": e.why_excluded,
        "feedback_event_id": str(e.feedback_event_id) if e.feedback_event_id else None,
        "feedback_label": e.feedback_label,
        "score_json": e.score_json,
        "usage_context": e.usage_context,
        "created_at": e.created_at.isoformat() if e.created_at else None,
        "updated_at": e.updated_at.isoformat() if e.updated_at else None,
    }
