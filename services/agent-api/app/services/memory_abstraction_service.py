"""Create, list, accept, and reject memory abstraction candidates."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.memory_abstraction_candidate import MemoryAbstractionCandidate
from app.db.models.memory import Memory
from app.db.models.growth import GrowthRecord
from app.db.models.memory_lifecycle_event import MemoryLifecycleEvent

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def create_candidate(data: dict) -> dict:
    with get_session() as s:
        ac = MemoryAbstractionCandidate(
            user_id=uuid.UUID(data["user_id"]),
            companion_id=uuid.UUID(data["companion_id"]),
            conversation_id=uuid.UUID(data["conversation_id"]) if data.get("conversation_id") else None,
            trace_run_id=uuid.UUID(data["trace_run_id"]) if data.get("trace_run_id") else None,
            source_memory_ids=[uuid.UUID(mid) for mid in data.get("source_memory_ids", [])],
            source_message_ids=[uuid.UUID(mid) for mid in data.get("source_message_ids", [])],
            source_feedback_event_ids=[uuid.UUID(fid) for fid in data.get("source_feedback_event_ids", [])],
            abstraction_type=data["abstraction_type"],
            title=data.get("title"),
            content=data["content"],
            summary=data.get("summary"),
            suggested_memory_type=data.get("suggested_memory_type"),
            suggested_growth_type=data.get("suggested_growth_type"),
            evidence_score=data.get("evidence_score", 0.0),
            confidence=data.get("confidence", 0.5),
            recurrence=data.get("recurrence", 0.0),
            consistency_score=data.get("consistency_score", 0.0),
            risk_score=data.get("risk_score", 0.0),
            reason=data.get("reason"),
            impact_preview=data.get("impact_preview", {}),
            evidence_json=data.get("evidence_json", {}),
            cluster_json=data.get("cluster_json", {}),
            status=data.get("status", "candidate"),
            expires_at=data.get("expires_at"),
        )
        s.add(ac)
        s.commit()
        s.refresh(ac)
        return _ac_dict(ac)


def list_candidates(
    companion_id: uuid.UUID | None = None,
    status: str | None = None,
    abstraction_type: str | None = None,
    page: int = 1, page_size: int = 20,
) -> dict:
    with get_session() as s:
        stmt = select(MemoryAbstractionCandidate)
        if companion_id:
            stmt = stmt.where(MemoryAbstractionCandidate.companion_id == companion_id)
        if status:
            stmt = stmt.where(MemoryAbstractionCandidate.status == status)
        if abstraction_type:
            stmt = stmt.where(MemoryAbstractionCandidate.abstraction_type == abstraction_type)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(MemoryAbstractionCandidate.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = [_ac_dict(ac) for ac in s.execute(stmt).scalars().all()]
        return {"items": items, "total": total}


def get_candidate(candidate_id: uuid.UUID) -> dict | None:
    with get_session() as s:
        ac = s.get(MemoryAbstractionCandidate, candidate_id)
        if not ac:
            return None
        return _ac_dict(ac)


def accept_as_memory(candidate_id: uuid.UUID, data: dict) -> dict:
    """Accept abstraction candidate and create a Memory record."""
    from app.services import memory_service

    with get_session() as read_session:
        source = read_session.get(MemoryAbstractionCandidate, candidate_id)
        if not source:
            return None
        prepared = memory_service.prepare_saved_memory_content(data.get("content") or source.content)

    with get_session() as s:
        ac = s.execute(
            select(MemoryAbstractionCandidate)
            .where(MemoryAbstractionCandidate.id == candidate_id)
            .with_for_update()
        ).scalar_one_or_none()
        if not ac:
            return None

        user_id = uuid.UUID(data.get("user_id", str(ac.user_id)))
        companion_id = uuid.UUID(data.get("companion_id", str(ac.companion_id)))

        # Create Memory from candidate content
        mem = Memory(
            user_id=user_id,
            companion_id=companion_id,
            owner_companion_id=companion_id,
            conversation_id=ac.conversation_id,
            memory_scope_type="private_companion",
            memory_layer="companion_private",
            type=data.get("memory_type") or ac.suggested_memory_type or "insight",
            content=prepared["content"],
            summary=data.get("summary") or ac.summary or ac.content[:200],
            source_message_ids=[str(mid) for mid in (ac.source_message_ids or [])],
            importance=max(0.5, ac.evidence_score or 0.5),
            confidence=ac.confidence or 0.5,
            memory_strength=max(0.5, ac.evidence_score or 0.5),
            abstraction_level=1,
            source_abstraction_candidate_id=ac.id,
            state="active",
            consent_status="user_confirmed",
        )
        memory_service.initialize_saved_memory_in_session(
            s, mem, prepared,
            reason=data.get("reason") or "user_committed_memory_abstraction",
        )

        # Update candidate
        ac.status = "committed_to_memory"
        ac.accepted_memory_id = mem.id
        ac.updated_at = datetime.now(timezone.utc)

        # Write MemoryLifecycleEvent
        mle = MemoryLifecycleEvent(
            user_id=user_id,
            companion_id=companion_id,
            conversation_id=ac.conversation_id,
            memory_id=mem.id,
            source_candidate_id=data.get("source_candidate_id"),
            event_type="abstraction_committed",
            title=f"Abstraction committed as memory: {ac.title or 'untitled'}",
            reason=data.get("reason") or ac.reason,
            new_state="active",
            new_strength=mem.memory_strength,
            new_confidence=mem.confidence,
            score_json={"evidence_score": ac.evidence_score, "confidence": ac.confidence},
            before_json={},
            after_json={"memory_id": str(mem.id), "abstraction_candidate_id": str(ac.id)},
        )
        s.add(mle)

        s.commit()
        s.refresh(ac)
        s.refresh(mem)
        return {
            "candidate": _ac_dict(ac),
            "memory": _mem_dict(mem),
        }


def accept_as_growth(candidate_id: uuid.UUID, data: dict) -> dict:
    """Accept abstraction candidate and create a GrowthRecord."""
    with get_session() as s:
        ac = s.get(MemoryAbstractionCandidate, candidate_id)
        if not ac:
            return None

        user_id = uuid.UUID(data.get("user_id", str(ac.user_id)))
        companion_id = uuid.UUID(data.get("companion_id", str(ac.companion_id)))

        # Create GrowthRecord from candidate content
        gr = GrowthRecord(
            user_id=user_id,
            companion_id=companion_id,
            source_candidate_id=None,
            source_abstraction_candidate_id=ac.id,
            type=ac.suggested_growth_type or "insight",
            content=ac.content,
            reason=ac.reason,
            evidence_memory_ids=[str(mid) for mid in (ac.source_memory_ids or [])],
            evidence_message_ids=[str(mid) for mid in (ac.source_message_ids or [])],
            impact_scope=[],
            applied_to_profile=False,
            status="committed",
        )
        s.add(gr)
        s.flush()

        # Update candidate
        ac.status = "committed_to_growth"
        ac.accepted_growth_record_id = gr.id
        ac.updated_at = datetime.now(timezone.utc)

        s.commit()
        s.refresh(ac)
        s.refresh(gr)
        return {
            "candidate": _ac_dict(ac),
            "growth_record": _gr_dict(gr),
        }


def edit_accept(candidate_id: uuid.UUID, data: dict) -> dict:
    """Update candidate with edited_content, set status to edited, then accept."""
    with get_session() as s:
        ac = s.get(MemoryAbstractionCandidate, candidate_id)
        if not ac:
            return None

        if "edited_content" in data and data["edited_content"] is not None:
            ac.edited_content = data["edited_content"]
            ac.content = data["edited_content"]

        if "title" in data and data["title"] is not None:
            ac.title = data["title"]

        ac.status = "edited"
        ac.updated_at = datetime.now(timezone.utc)

        s.commit()
        s.refresh(ac)
        return _ac_dict(ac)


def reject_candidate(candidate_id: uuid.UUID, data: dict) -> dict:
    """Update candidate status to rejected, set rejection_reason."""
    with get_session() as s:
        ac = s.get(MemoryAbstractionCandidate, candidate_id)
        if not ac:
            return None

        ac.status = "rejected"
        ac.rejection_reason = data.get("rejection_reason") or data.get("reason")
        ac.updated_at = datetime.now(timezone.utc)

        s.commit()
        s.refresh(ac)
        return _ac_dict(ac)


def _ac_dict(ac: MemoryAbstractionCandidate) -> dict:
    return {
        "id": str(ac.id),
        "user_id": str(ac.user_id),
        "companion_id": str(ac.companion_id),
        "conversation_id": str(ac.conversation_id) if ac.conversation_id else None,
        "trace_run_id": str(ac.trace_run_id) if ac.trace_run_id else None,
        "source_memory_ids": [str(mid) for mid in (ac.source_memory_ids or [])],
        "source_message_ids": [str(mid) for mid in (ac.source_message_ids or [])],
        "source_feedback_event_ids": [str(fid) for fid in (ac.source_feedback_event_ids or [])],
        "abstraction_type": ac.abstraction_type,
        "title": ac.title,
        "content": ac.content,
        "summary": ac.summary,
        "suggested_memory_type": ac.suggested_memory_type,
        "suggested_growth_type": ac.suggested_growth_type,
        "evidence_score": ac.evidence_score,
        "confidence": ac.confidence,
        "recurrence": ac.recurrence,
        "consistency_score": ac.consistency_score,
        "risk_score": ac.risk_score,
        "reason": ac.reason,
        "impact_preview": ac.impact_preview,
        "evidence_json": ac.evidence_json,
        "cluster_json": ac.cluster_json,
        "status": ac.status,
        "accepted_memory_id": str(ac.accepted_memory_id) if ac.accepted_memory_id else None,
        "accepted_growth_record_id": str(ac.accepted_growth_record_id) if ac.accepted_growth_record_id else None,
        "edited_content": ac.edited_content,
        "rejection_reason": ac.rejection_reason,
        "expires_at": ac.expires_at.isoformat() if ac.expires_at else None,
        "created_at": ac.created_at.isoformat() if ac.created_at else None,
        "updated_at": ac.updated_at.isoformat() if ac.updated_at else None,
    }


def _mem_dict(m: Memory) -> dict:
    return {
        "id": str(m.id),
        "type": m.type,
        "state": m.state,
        "content": m.content,
        "summary": m.summary,
        "importance": m.importance,
        "confidence": m.confidence,
        "memory_strength": m.memory_strength,
        "abstraction_level": m.abstraction_level,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def _gr_dict(r: GrowthRecord) -> dict:
    return {
        "id": str(r.id),
        "type": r.type,
        "content": r.content,
        "reason": r.reason,
        "status": r.status,
        "applied_to_profile": r.applied_to_profile,
        "source_abstraction_candidate_id": str(r.source_abstraction_candidate_id) if r.source_abstraction_candidate_id else None,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "updated_at": r.updated_at.isoformat() if r.updated_at else None,
    }
