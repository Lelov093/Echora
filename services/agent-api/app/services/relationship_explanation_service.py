"""Create, list, and get relationship explanation events."""

import uuid

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.relationship_explanation_event import RelationshipExplanationEvent

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def create_explanation(data: dict) -> dict:
    with get_session() as s:
        re = RelationshipExplanationEvent(
            user_id=uuid.UUID(data["user_id"]),
            companion_id=uuid.UUID(data["companion_id"]),
            conversation_id=uuid.UUID(data["conversation_id"]) if data.get("conversation_id") else None,
            trace_run_id=uuid.UUID(data["trace_run_id"]) if data.get("trace_run_id") else None,
            relationship_event_id=uuid.UUID(data["relationship_event_id"]) if data.get("relationship_event_id") else None,
            feedback_event_id=uuid.UUID(data["feedback_event_id"]) if data.get("feedback_event_id") else None,
            dimension=data["dimension"],
            previous_value=data.get("previous_value"),
            new_value=data.get("new_value"),
            delta=data.get("delta"),
            title=data.get("title"),
            explanation=data["explanation"],
            evidence_memory_ids=[uuid.UUID(mid) for mid in data.get("evidence_memory_ids", [])],
            evidence_message_ids=[uuid.UUID(mid) for mid in data.get("evidence_message_ids", [])],
            evidence_growth_record_ids=[uuid.UUID(gid) for gid in data.get("evidence_growth_record_ids", [])],
            confidence=data.get("confidence", 0.5),
            user_visible=data.get("user_visible", True),
            user_confirmed=data.get("user_confirmed", False),
            score_json=data.get("score_json", {}),
            impact_json=data.get("impact_json", {}),
        )
        s.add(re)
        s.commit()
        s.refresh(re)
        return _re_dict(re)


def list_explanations(
    companion_id: uuid.UUID | None = None,
    dimension: str | None = None,
    page: int = 1, page_size: int = 20,
) -> dict:
    with get_session() as s:
        stmt = select(RelationshipExplanationEvent)
        if companion_id:
            stmt = stmt.where(RelationshipExplanationEvent.companion_id == companion_id)
        if dimension:
            stmt = stmt.where(RelationshipExplanationEvent.dimension == dimension)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(RelationshipExplanationEvent.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = [_re_dict(re) for re in s.execute(stmt).scalars().all()]
        return {"items": items, "total": total}


def get_explanation(explanation_id: uuid.UUID) -> dict | None:
    with get_session() as s:
        re = s.get(RelationshipExplanationEvent, explanation_id)
        if not re:
            return None
        return _re_dict(re)


def list_for_companion(companion_id: uuid.UUID, page: int = 1, page_size: int = 20) -> dict:
    return list_explanations(companion_id=companion_id, page=page, page_size=page_size)


def _re_dict(re: RelationshipExplanationEvent) -> dict:
    return {
        "id": str(re.id),
        "user_id": str(re.user_id),
        "companion_id": str(re.companion_id),
        "conversation_id": str(re.conversation_id) if re.conversation_id else None,
        "trace_run_id": str(re.trace_run_id) if re.trace_run_id else None,
        "relationship_event_id": str(re.relationship_event_id) if re.relationship_event_id else None,
        "feedback_event_id": str(re.feedback_event_id) if re.feedback_event_id else None,
        "dimension": re.dimension,
        "previous_value": re.previous_value,
        "new_value": re.new_value,
        "delta": re.delta,
        "title": re.title,
        "explanation": re.explanation,
        "evidence_memory_ids": [str(mid) for mid in (re.evidence_memory_ids or [])],
        "evidence_message_ids": [str(mid) for mid in (re.evidence_message_ids or [])],
        "evidence_growth_record_ids": [str(gid) for gid in (re.evidence_growth_record_ids or [])],
        "confidence": re.confidence,
        "user_visible": re.user_visible,
        "user_confirmed": re.user_confirmed,
        "score_json": re.score_json,
        "impact_json": re.impact_json,
        "created_at": re.created_at.isoformat() if re.created_at else None,
        "updated_at": re.updated_at.isoformat() if re.updated_at else None,
    }
