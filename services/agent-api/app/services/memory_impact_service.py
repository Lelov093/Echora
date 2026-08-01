"""Build an impact summary for a memory."""

import uuid

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.memory import Memory
from app.db.models.memory_usage_event import MemoryUsageEvent
from app.db.models.feedback_event import FeedbackEvent

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def get_memory_impact(memory_id: uuid.UUID) -> dict:
    with get_session() as s:
        mem = s.get(Memory, memory_id)
        if not mem:
            return None

        # Overview
        overview = {
            "id": str(mem.id),
            "type": mem.type,
            "state": mem.state,
            "visibility": mem.visibility,
            "consent_status": mem.consent_status,
            "memory_strength": mem.memory_strength,
            "importance": mem.importance,
            "confidence": mem.confidence,
            "goal_relevance": mem.goal_relevance,
            "relationship_impact": mem.relationship_impact,
            "emotional_intensity": mem.emotional_intensity,
            "feedback_score": mem.feedback_score,
            "helpful_count": mem.helpful_count,
            "irrelevant_count": mem.irrelevant_count,
            "outdated_count": mem.outdated_count,
            "wrong_count": mem.wrong_count,
            "reactivation_count": mem.reactivation_count,
            "half_life_days": mem.half_life_days,
            "last_feedback_at": mem.last_feedback_at.isoformat() if mem.last_feedback_at else None,
            "last_used_in_response_at": mem.last_used_in_response_at.isoformat() if mem.last_used_in_response_at else None,
            "created_at": mem.created_at.isoformat() if mem.created_at else None,
            "updated_at": mem.updated_at.isoformat() if mem.updated_at else None,
        }

        # Query all usage events for this memory
        usage_stmt = select(MemoryUsageEvent).where(
            MemoryUsageEvent.memory_id == memory_id
        ).order_by(MemoryUsageEvent.created_at.desc())
        usage_events = s.execute(usage_stmt).scalars().all()

        # Recent usage (all usage events as refs)
        recent_usage = []
        growth_impact = []
        presence_impact = []
        relationship_impact = []

        for e in usage_events:
            ref = {
                "id": str(e.id),
                "event_type": e.event_type,
                "created_at": e.created_at.isoformat() if e.created_at else None,
                "conversation_id": str(e.conversation_id) if e.conversation_id else None,
                "trace_run_id": str(e.trace_run_id) if e.trace_run_id else None,
                "retrieval_score": e.retrieval_score,
                "used_in_response": e.used_in_response,
                "used_in_growth": e.used_in_growth,
                "used_in_presence": e.used_in_presence,
                "used_in_relationship": e.used_in_relationship,
            }
            recent_usage.append(ref)

            if e.used_in_growth:
                growth_impact.append(ref)
            if e.used_in_presence:
                presence_impact.append(ref)
            if e.used_in_relationship:
                relationship_impact.append(ref)

        # Query feedback events referencing this memory
        fb_stmt = select(FeedbackEvent).where(
            FeedbackEvent.target_id == memory_id,
            FeedbackEvent.applies_to_memory == True,
        ).order_by(FeedbackEvent.created_at.desc())
        fb_events = s.execute(fb_stmt).scalars().all()
        feedback_events = []
        for fe in fb_events:
            feedback_events.append({
                "id": str(fe.id),
                "user_id": str(fe.user_id),
                "companion_id": str(fe.companion_id),
                "action": fe.action,
                "label": fe.label,
                "reason": fe.reason,
                "user_note": fe.user_note,
                "calibration_status": fe.calibration_status,
                "applied_at": fe.applied_at.isoformat() if fe.applied_at else None,
                "score_delta": fe.score_delta,
                "strength_delta": fe.strength_delta,
                "created_at": fe.created_at.isoformat() if fe.created_at else None,
            })

        return {
            "overview": overview,
            "recent_usage": recent_usage,
            "growth_impact": growth_impact,
            "presence_impact": presence_impact,
            "relationship_impact": relationship_impact,
            "feedback_events": feedback_events,
        }
