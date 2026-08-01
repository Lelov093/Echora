"""Companion companion-private memory query service."""

import uuid
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Memory

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def list_companion_memories(
    companion_id: uuid.UUID,
    state: str | None = None,
    scope_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(Memory).where(
            Memory.deleted_at.is_(None),
            Memory.owner_companion_id == companion_id,
            Memory.memory_scope_type.in_(("legacy_private", "private_companion", "relationship")),
        )
        if state:
            stmt = stmt.where(Memory.state == state)
        if scope_type:
            stmt = stmt.where(Memory.memory_scope_type == scope_type)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(Memory.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def get_companion_memory(memory_id: uuid.UUID, companion_id: uuid.UUID) -> Memory | None:
    with get_session() as s:
        return s.execute(
            select(Memory).where(
                Memory.id == memory_id,
                Memory.owner_companion_id == companion_id,
                Memory.deleted_at.is_(None),
            )
        ).scalar_one_or_none()


def _memory_dict(memory: Memory) -> dict[str, Any]:
    return {
        "id": str(memory.id),
        "user_id": str(memory.user_id),
        "companion_id": str(memory.companion_id),
        "owner_companion_id": str(memory.owner_companion_id) if memory.owner_companion_id else None,
        "shared_memory_id": str(memory.shared_memory_id) if memory.shared_memory_id else None,
        "memory_scope_type": memory.memory_scope_type,
        "memory_layer": memory.memory_layer,
        "type": memory.type,
        "state": memory.state,
        "visibility": memory.visibility,
        "consent_status": memory.consent_status,
        "content": memory.content,
        "summary": memory.summary,
        "importance": memory.importance,
        "confidence": memory.confidence,
        "memory_strength": memory.memory_strength,
        "visibility_policy_json": memory.visibility_policy_json or {},
        "created_at": memory.created_at.isoformat() if memory.created_at else None,
        "updated_at": memory.updated_at.isoformat() if memory.updated_at else None,
    }
