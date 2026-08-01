"""Bad Case service layer."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import BadCase

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def list_bad_cases(companion_id: uuid.UUID | None = None, type_: str | None = None,
                   status: str | None = None, page: int = 1, page_size: int = 20) -> dict:
    with get_session() as s:
        stmt = select(BadCase)
        if companion_id:
            stmt = stmt.where(BadCase.companion_id == companion_id)
        if type_:
            stmt = stmt.where(BadCase.type == type_)
        if status:
            stmt = stmt.where(BadCase.status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(BadCase.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def create_bad_case(data: dict) -> BadCase:
    with get_session() as s:
        bc = BadCase(**data)
        s.add(bc)
        s.commit()
        s.refresh(bc)
        return bc


def update_bad_case(bad_case_id: uuid.UUID, data: dict) -> BadCase | None:
    with get_session() as s:
        bc = s.get(BadCase, bad_case_id)
        if not bc:
            return None
        for k, v in data.items():
            if v is not None and hasattr(bc, k):
                setattr(bc, k, v)
        if data.get("status") == "resolved":
            bc.resolved_at = datetime.now(timezone.utc)
        bc.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(bc)
        return bc


def _bc_dict(bc: BadCase) -> dict:
    return {
        "id": str(bc.id), "type": bc.type, "title": bc.title,
        "severity": bc.severity, "status": bc.status,
        "description": bc.description, "resolution": bc.resolution,
        "created_at": bc.created_at.isoformat() if bc.created_at else None,
    }
