"""Create, list, refresh, and correct continuity snapshots."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select, func, update as sa_update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.continuity_snapshot import ContinuitySnapshot
from app.db.models.conversation import Conversation
from app.db.models.message import Message

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def create_snapshot(data: dict) -> dict:
    with get_session() as s:
        cs = ContinuitySnapshot(
            user_id=uuid.UUID(data["user_id"]),
            companion_id=uuid.UUID(data["companion_id"]),
            conversation_id=uuid.UUID(data["conversation_id"]) if data.get("conversation_id") else None,
            trace_run_id=uuid.UUID(data["trace_run_id"]) if data.get("trace_run_id") else None,
            snapshot_type=data.get("snapshot_type", "agent_run"),
            mode_key=data.get("mode_key", "project"),
            current_topic=data.get("current_topic"),
            current_goal=data.get("current_goal"),
            current_phase=data.get("current_phase"),
            last_user_intent=data.get("last_user_intent"),
            last_assistant_summary=data.get("last_assistant_summary"),
            open_threads=data.get("open_threads", []),
            unresolved_decisions=data.get("unresolved_decisions", []),
            pending_reviews=data.get("pending_reviews", []),
            suggested_next_steps=data.get("suggested_next_steps", []),
            relevant_memory_ids=data.get("relevant_memory_ids", []),
            relevant_growth_record_ids=data.get("relevant_growth_record_ids", []),
            relevant_presence_opportunity_ids=data.get("relevant_presence_opportunity_ids", []),
            continuity_score=data.get("continuity_score", 0.5),
            freshness_score=data.get("freshness_score", 0.5),
            user_confirmed=data.get("user_confirmed", False),
            feedback_event_id=uuid.UUID(data["feedback_event_id"]) if data.get("feedback_event_id") else None,
            snapshot_json=data.get("snapshot_json", {}),
        )
        s.add(cs)
        s.commit()
        s.refresh(cs)
        return _cs_dict(cs)


def list_snapshots(
    companion_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
    snapshot_type: str | None = None,
    page: int = 1, page_size: int = 20,
) -> dict:
    with get_session() as s:
        stmt = select(ContinuitySnapshot)
        if companion_id:
            stmt = stmt.where(ContinuitySnapshot.companion_id == companion_id)
        if conversation_id:
            stmt = stmt.where(ContinuitySnapshot.conversation_id == conversation_id)
        if snapshot_type:
            stmt = stmt.where(ContinuitySnapshot.snapshot_type == snapshot_type)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(ContinuitySnapshot.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = [_cs_dict(cs) for cs in s.execute(stmt).scalars().all()]
        return {"items": items, "total": total}


def get_snapshot(snapshot_id: uuid.UUID) -> dict | None:
    with get_session() as s:
        cs = s.get(ContinuitySnapshot, snapshot_id)
        if not cs:
            return None
        return _cs_dict(cs)


def refresh_continuity(data: dict) -> dict:
    """Create a new snapshot and update conversation continuity state.

    If conversation_id is given, queries recent messages and pending counts.
    Stores open_threads/pending_reviews as JSONB.
    Updates conversations.latest_continuity_snapshot_id.
    """
    with get_session() as s:
        conversation_id = uuid.UUID(data["conversation_id"]) if data.get("conversation_id") else None

        open_threads = data.get("open_threads", [])
        pending_reviews = data.get("pending_reviews", [])
        unresolved_decisions = data.get("unresolved_decisions", [])

        # If conversation_id is provided, query recent messages and pending counts
        if conversation_id:
            # Query the 10 most recent messages for context
            msg_stmt = (
                select(Message)
                .where(Message.conversation_id == conversation_id)
                .order_by(Message.created_at.desc())
                .limit(10)
            )
            recent_messages = s.execute(msg_stmt).scalars().all()
            if recent_messages and not open_threads:
                # Derive open threads from recent messages if not explicitly provided
                open_threads = [
                    {"role": msg.role, "content_preview": msg.content[:200] if msg.content else ""}
                    for msg in reversed(recent_messages)
                ]

        cs = ContinuitySnapshot(
            user_id=uuid.UUID(data["user_id"]),
            companion_id=uuid.UUID(data["companion_id"]),
            conversation_id=conversation_id,
            trace_run_id=uuid.UUID(data["trace_run_id"]) if data.get("trace_run_id") else None,
            snapshot_type=data.get("snapshot_type", "manual_refresh"),
            mode_key=data.get("mode_key", "project"),
            current_topic=data.get("current_topic"),
            current_goal=data.get("current_goal"),
            current_phase=data.get("current_phase"),
            last_user_intent=data.get("last_user_intent"),
            last_assistant_summary=data.get("last_assistant_summary"),
            open_threads=open_threads,
            unresolved_decisions=unresolved_decisions,
            pending_reviews=pending_reviews,
            suggested_next_steps=data.get("suggested_next_steps", []),
            relevant_memory_ids=data.get("relevant_memory_ids", []),
            relevant_growth_record_ids=data.get("relevant_growth_record_ids", []),
            relevant_presence_opportunity_ids=data.get("relevant_presence_opportunity_ids", []),
            continuity_score=data.get("continuity_score", 0.5),
            freshness_score=data.get("freshness_score", 0.5),
            user_confirmed=data.get("user_confirmed", False),
            feedback_event_id=uuid.UUID(data["feedback_event_id"]) if data.get("feedback_event_id") else None,
            snapshot_json=data.get("snapshot_json", {}),
        )
        s.add(cs)
        s.flush()

        # Update conversation's latest_continuity_snapshot_id and continuity state
        if conversation_id:
            conv = s.get(Conversation, conversation_id)
            if conv:
                conv.latest_continuity_snapshot_id = cs.id
                conv.continuity_updated_at = datetime.now(timezone.utc)
                conv.open_thread_count = len(open_threads)
                conv.pending_review_count = len(pending_reviews)
                conv.unresolved_decision_count = len(unresolved_decisions)
                if data.get("suggested_next_steps"):
                    conv.next_step_summary = str(data.get("suggested_next_steps"))
                if data.get("continuity_score"):
                    conv.continuity_score = data["continuity_score"]
                if data.get("current_topic"):
                    conv.current_topic = data["current_topic"]

        s.commit()
        s.refresh(cs)
        return _cs_dict(cs)


def correct_continuity(snapshot_id: uuid.UUID, data: dict) -> dict:
    """Update current_topic, current_goal, open_threads, suggested_next_steps of an existing snapshot."""
    with get_session() as s:
        cs = s.get(ContinuitySnapshot, snapshot_id)
        if not cs:
            return None

        if "current_topic" in data and data["current_topic"] is not None:
            cs.current_topic = data["current_topic"]
        if "current_goal" in data and data["current_goal"] is not None:
            cs.current_goal = data["current_goal"]
        if "open_threads" in data and data["open_threads"] is not None:
            cs.open_threads = data["open_threads"]
        if "suggested_next_steps" in data and data["suggested_next_steps"] is not None:
            cs.suggested_next_steps = data["suggested_next_steps"]
        if "user_confirmed" in data:
            cs.user_confirmed = data["user_confirmed"]

        s.commit()
        s.refresh(cs)
        return _cs_dict(cs)


def get_conversation_continuity(conversation_id: uuid.UUID) -> dict:
    """Get the latest continuity snapshot for a conversation."""
    with get_session() as s:
        stmt = (
            select(ContinuitySnapshot)
            .where(ContinuitySnapshot.conversation_id == conversation_id)
            .order_by(ContinuitySnapshot.created_at.desc())
            .limit(1)
        )
        cs = s.execute(stmt).scalars().first()
        if not cs:
            return None
        return _cs_dict(cs)


def _cs_dict(cs: ContinuitySnapshot) -> dict:
    return {
        "id": str(cs.id),
        "user_id": str(cs.user_id),
        "companion_id": str(cs.companion_id),
        "conversation_id": str(cs.conversation_id) if cs.conversation_id else None,
        "trace_run_id": str(cs.trace_run_id) if cs.trace_run_id else None,
        "snapshot_type": cs.snapshot_type,
        "mode_key": cs.mode_key,
        "current_topic": cs.current_topic,
        "current_goal": cs.current_goal,
        "current_phase": cs.current_phase,
        "last_user_intent": cs.last_user_intent,
        "last_assistant_summary": cs.last_assistant_summary,
        "open_threads": cs.open_threads,
        "unresolved_decisions": cs.unresolved_decisions,
        "pending_reviews": cs.pending_reviews,
        "suggested_next_steps": cs.suggested_next_steps,
        "relevant_memory_ids": [str(mid) for mid in (cs.relevant_memory_ids or [])],
        "relevant_growth_record_ids": [str(gid) for gid in (cs.relevant_growth_record_ids or [])],
        "relevant_presence_opportunity_ids": [str(pid) for pid in (cs.relevant_presence_opportunity_ids or [])],
        "continuity_score": cs.continuity_score,
        "freshness_score": cs.freshness_score,
        "user_confirmed": cs.user_confirmed,
        "feedback_event_id": str(cs.feedback_event_id) if cs.feedback_event_id else None,
        "snapshot_json": cs.snapshot_json,
        "created_at": cs.created_at.isoformat() if cs.created_at else None,
        "updated_at": cs.updated_at.isoformat() if cs.updated_at else None,
    }
