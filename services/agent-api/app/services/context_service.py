"""Project & Creative Context service layer."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import ProjectContext, CreativeContext

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


# ── Project Context ──────────────────────────────────────────────────

def list_project_contexts(companion_id: uuid.UUID | None = None, page: int = 1, page_size: int = 20) -> dict:
    with get_session() as s:
        stmt = select(ProjectContext)
        if companion_id:
            stmt = stmt.where(ProjectContext.companion_id == companion_id)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(ProjectContext.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def get_project_context(context_id: uuid.UUID) -> ProjectContext | None:
    with get_session() as s:
        return s.get(ProjectContext, context_id)


def create_project_context(data: dict) -> ProjectContext:
    with get_session() as s:
        ctx = ProjectContext(**data)
        s.add(ctx)
        s.commit()
        s.refresh(ctx)
        return ctx


def update_project_context(context_id: uuid.UUID, data: dict) -> ProjectContext | None:
    with get_session() as s:
        ctx = s.get(ProjectContext, context_id)
        if not ctx:
            return None
        for k, v in data.items():
            if v is not None and hasattr(ctx, k):
                setattr(ctx, k, v)
        ctx.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(ctx)
        return ctx


# ── Creative Context ─────────────────────────────────────────────────

def list_creative_contexts(companion_id: uuid.UUID | None = None, page: int = 1, page_size: int = 20) -> dict:
    with get_session() as s:
        stmt = select(CreativeContext)
        if companion_id:
            stmt = stmt.where(CreativeContext.companion_id == companion_id)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(CreativeContext.updated_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def get_creative_context(context_id: uuid.UUID) -> CreativeContext | None:
    with get_session() as s:
        return s.get(CreativeContext, context_id)


def create_creative_context(data: dict) -> CreativeContext:
    with get_session() as s:
        ctx = CreativeContext(**data)
        s.add(ctx)
        s.commit()
        s.refresh(ctx)
        return ctx


def update_creative_context(context_id: uuid.UUID, data: dict) -> CreativeContext | None:
    with get_session() as s:
        ctx = s.get(CreativeContext, context_id)
        if not ctx:
            return None
        for k, v in data.items():
            if v is not None and hasattr(ctx, k):
                setattr(ctx, k, v)
        ctx.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(ctx)
        return ctx
