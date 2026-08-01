"""Canonical BoundarySetting-backed controls for Growth suggestions."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import BoundarySetting, Companion

_engine = None


class GrowthControlError(ValueError):
    def __init__(self, code: str, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def get_policy(companion_id: uuid.UUID) -> dict:
    with get_session() as session:
        companion = session.get(Companion, companion_id)
        if companion is None or companion.deleted_at is not None:
            raise GrowthControlError("COMPANION_NOT_FOUND", "Companion not found.")
        row = session.execute(
            select(BoundarySetting).where(
                BoundarySetting.companion_id == companion_id,
                BoundarySetting.user_id == companion.user_id,
            )
        ).scalar_one_or_none()
        return _policy_dict(companion_id, row)


def update_policy(
    companion_id: uuid.UUID,
    *,
    suggestions_enabled: bool,
    paused_types: list[str],
    expected_updated_at: datetime | None,
) -> dict:
    with get_session() as session:
        companion = session.execute(
            select(Companion).where(
                Companion.id == companion_id,
                Companion.deleted_at.is_(None),
            ).with_for_update()
        ).scalar_one_or_none()
        if companion is None:
            raise GrowthControlError("COMPANION_NOT_FOUND", "Companion not found.")
        row = session.execute(
            select(BoundarySetting).where(
                BoundarySetting.companion_id == companion_id,
                BoundarySetting.user_id == companion.user_id,
            ).with_for_update()
        ).scalar_one_or_none()
        if row is not None and expected_updated_at != row.updated_at:
            raise GrowthControlError(
                "GROWTH_POLICY_CONFLICT",
                "Growth settings changed after they were loaded.",
                {
                    "expected_updated_at": (
                        expected_updated_at.isoformat() if expected_updated_at else None
                    ),
                    "current_updated_at": row.updated_at.isoformat() if row.updated_at else None,
                },
            )
        if row is None and expected_updated_at is not None:
            raise GrowthControlError(
                "GROWTH_POLICY_CONFLICT",
                "Growth settings were created after they were loaded.",
            )
        if row is None:
            row = BoundarySetting(
                user_id=companion.user_id,
                companion_id=companion_id,
            )
            session.add(row)
        row.growth_confirmation_policy = {
            "suggestions_enabled": suggestions_enabled,
            "paused_types": sorted(set(paused_types)),
        }
        row.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(row)
        return _policy_dict(companion_id, row)


def suggestions_allowed(
    companion_id: uuid.UUID,
    suggestion_type: str | None = None,
    *,
    session: Session | None = None,
) -> bool:
    owns_session = session is None
    active_session = session or get_session()
    try:
        row = active_session.execute(
            select(BoundarySetting).where(BoundarySetting.companion_id == companion_id)
        ).scalar_one_or_none()
        stored = dict(row.growth_confirmation_policy or {}) if row else {}
        if stored.get("suggestions_enabled", True) is False:
            return False
        paused = {str(item) for item in stored.get("paused_types", [])}
        return suggestion_type is None or suggestion_type not in paused
    finally:
        if owns_session:
            active_session.close()


def _policy_dict(companion_id: uuid.UUID, row: BoundarySetting | None) -> dict:
    stored = dict(row.growth_confirmation_policy or {}) if row else {}
    return {
        "contract_version": "growth-suggestion-policy.v1",
        "companion_id": str(companion_id),
        "suggestions_enabled": stored.get("suggestions_enabled", True) is not False,
        "paused_types": sorted({str(item) for item in stored.get("paused_types", [])}),
        "updated_at": row.updated_at.isoformat() if row and row.updated_at else None,
    }
