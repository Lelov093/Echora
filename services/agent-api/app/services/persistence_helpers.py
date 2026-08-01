"""Shared persistence helpers for domain services."""

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Companion, User

_engine = None


def get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(get_engine())


def default_ids(session: Session) -> tuple[uuid.UUID, uuid.UUID]:
    user = session.query(User).first()
    companion = session.query(Companion).first()
    return (
        user.id if user else uuid.uuid4(),
        companion.id if companion else uuid.uuid4(),
    )


def as_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def normalize_payload(data: dict[str, Any]) -> dict[str, Any]:
    normalized = {}
    for key, value in data.items():
        if key.endswith("_id") and value not in (None, ""):
            normalized[key] = as_uuid(value)
        else:
            normalized[key] = value
    return normalized


def row_to_dict(obj: Any) -> dict[str, Any]:
    result = {}
    for col in obj.__table__.columns:
        key = "metadata" if col.name == "metadata" else col.name
        attr = "metadata_" if col.name == "metadata" else col.name
        value = getattr(obj, attr)
        if isinstance(value, uuid.UUID):
            value = str(value)
        elif isinstance(value, (datetime, date)):
            value = value.isoformat()
        elif isinstance(value, list):
            value = [str(v) if isinstance(v, uuid.UUID) else v for v in value]
        result[key] = value
    return result


def list_rows(session: Session, model: type, filters: dict[str, Any], page: int, page_size: int) -> dict:
    stmt = select(model).where(getattr(model, "deleted_at", None).is_(None)) if hasattr(model, "deleted_at") else select(model)
    for key, value in filters.items():
        if value in (None, "") or not hasattr(model, key):
            continue
        stmt = stmt.where(getattr(model, key) == value)
    total = session.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    items = session.execute(
        stmt.order_by(model.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    ).scalars().all()
    return {"items": [row_to_dict(item) for item in items], "total": total}


def create_row(session: Session, model: type, data: dict[str, Any]):
    row = model(**normalize_payload(data))
    session.add(row)
    session.commit()
    session.refresh(row)
    return row_to_dict(row)


def update_row(session: Session, model: type, row_id: uuid.UUID, data: dict[str, Any]) -> dict | None:
    row = session.get(model, row_id)
    if row is None:
        return None
    for key, value in normalize_payload(data).items():
        if value is not None and hasattr(row, key):
            setattr(row, key, value)
    session.commit()
    session.refresh(row)
    return row_to_dict(row)
