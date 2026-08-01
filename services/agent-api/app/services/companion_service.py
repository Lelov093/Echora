"""Companion service layer."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Companion, CompanionMode, Conversation, Memory, MemoryCandidate, GrowthCandidate, PresenceOpportunity

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


# ── Companion CRUD ───────────────────────────────────────────────────

def list_companions(user_id: uuid.UUID | None = None) -> list[Companion]:
    with get_session() as s:
        stmt = select(Companion).where(Companion.deleted_at.is_(None))
        if user_id:
            stmt = stmt.where(Companion.user_id == user_id)
        stmt = stmt.order_by(Companion.created_at.desc())
        return list(s.execute(stmt).scalars().all())


def get_companion(companion_id: uuid.UUID) -> Companion | None:
    with get_session() as s:
        return s.get(Companion, companion_id)


def create_companion(data: dict) -> Companion:
    with get_session() as s:
        c = Companion(**data)
        s.add(c)
        s.commit()
        s.refresh(c)
        return c


def update_companion(companion_id: uuid.UUID, data: dict) -> Companion | None:
    with get_session() as s:
        c = s.get(Companion, companion_id)
        if not c:
            return None
        for k, v in data.items():
            if v is not None and hasattr(c, k):
                setattr(c, k, v)
        c.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(c)
        return c


# ── Companion Modes ──────────────────────────────────────────────────

def list_modes(companion_id: uuid.UUID) -> list[CompanionMode]:
    with get_session() as s:
        return list(
            s.execute(
                select(CompanionMode)
                .where(CompanionMode.companion_id == companion_id)
                .order_by(CompanionMode.mode_key)
            ).scalars().all()
        )


def switch_mode(companion_id: uuid.UUID, mode_key: str) -> Companion | None:
    with get_session() as s:
        c = s.get(Companion, companion_id)
        if not c:
            return None
        mode = s.execute(
            select(CompanionMode).where(
                CompanionMode.companion_id == companion_id,
                CompanionMode.mode_key == mode_key,
            )
        ).scalar_one_or_none()
        if not mode or not mode.is_enabled:
            return None
        c.current_mode = mode_key
        c.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(c)
        return c


# ── Companion Hub ────────────────────────────────────────────────────

def get_hub(companion_id: uuid.UUID) -> dict:
    with get_session() as s:
        c = s.get(Companion, companion_id)
        if not c:
            return {}

        # Last continuity from latest active conversation
        last_conv = s.execute(
            select(Conversation)
            .where(Conversation.companion_id == companion_id, Conversation.status == "active")
            .order_by(Conversation.updated_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        # Counts
        active_memories = s.execute(
            select(func.count(Memory.id)).where(
                Memory.companion_id == companion_id, Memory.state == "active"
            )
        ).scalar()
        pending_memory_candidates = s.execute(
            select(func.count(MemoryCandidate.id)).where(
                MemoryCandidate.companion_id == companion_id,
                MemoryCandidate.status == "pending",
            )
        ).scalar()
        pending_growth = s.execute(
            select(func.count(GrowthCandidate.id)).where(
                GrowthCandidate.companion_id == companion_id,
                GrowthCandidate.status == "candidate",
            )
        ).scalar()
        queued_presence = s.execute(
            select(func.count(PresenceOpportunity.id)).where(
                PresenceOpportunity.companion_id == companion_id,
                PresenceOpportunity.status == "queued",
            )
        ).scalar()

        # Recent memories (top 3)
        recent_memories = list(
            s.execute(
                select(Memory)
                .where(Memory.companion_id == companion_id, Memory.state == "active")
                .order_by(Memory.updated_at.desc())
                .limit(3)
            ).scalars().all()
        )

        # Presence preview (top 3 queued)
        presence_preview = list(
            s.execute(
                select(PresenceOpportunity)
                .where(
                    PresenceOpportunity.companion_id == companion_id,
                    PresenceOpportunity.status == "queued",
                )
                .order_by(PresenceOpportunity.priority.desc())
                .limit(3)
            ).scalars().all()
        )

        return {
            "companion": _companion_to_dict(c),
            "last_continuity": {
                "conversation_id": str(last_conv.id) if last_conv else None,
                "current_topic": last_conv.current_topic if last_conv else None,
                "current_goal": last_conv.current_goal if last_conv else None,
                "last_message_at": last_conv.updated_at.isoformat() if last_conv else None,
            },
            "recent_memories": [_memory_summary(m) for m in recent_memories],
            "presence_preview": [_presence_summary(p) for p in presence_preview],
            "stats": {
                "active_memories": active_memories or 0,
                "pending_memory_candidates": pending_memory_candidates or 0,
                "pending_growth_candidates": pending_growth or 0,
                "queued_presence_opportunities": queued_presence or 0,
            },
        }


# ── Serialization helpers ────────────────────────────────────────────

def _companion_to_dict(c: Companion) -> dict:
    return {
        "id": str(c.id),
        "name": c.name,
        "subtitle": c.subtitle,
        "base_personality": c.base_personality,
        "current_mode": c.current_mode,
        "current_status": c.current_status,
        "current_focus": c.current_focus,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
    }


def _memory_summary(m: Memory) -> dict:
    return {
        "id": str(m.id),
        "type": m.type,
        "summary": m.summary,
        "state": m.state,
        "memory_strength": m.memory_strength,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def _presence_summary(p: PresenceOpportunity) -> dict:
    return {
        "id": str(p.id),
        "type": p.type,
        "title": p.title,
        "priority": p.priority,
        "status": p.status,
    }
