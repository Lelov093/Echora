"""Boundary Settings service layer."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings as app_settings
from app.db.models import BoundarySetting, Companion

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(app_settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def get_settings(companion_id: uuid.UUID, user_id: uuid.UUID | None = None) -> BoundarySetting | None:
    with get_session() as s:
        row = s.execute(
            select(BoundarySetting).where(BoundarySetting.companion_id == companion_id)
        ).scalar_one_or_none()
        if row is not None and user_id is not None and row.user_id != user_id:
            return None
        return row


def update_settings(
    companion_id: uuid.UUID,
    user_id: uuid.UUID | None,
    data: dict,
) -> BoundarySetting:
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if companion is None or companion.deleted_at is not None:
            raise ValueError("Companion not found")
        owner_id = companion.user_id
        if user_id is not None and user_id != owner_id:
            raise ValueError("Presence policy owner/Companion scope is invalid")
        bs = s.execute(
            select(BoundarySetting).where(BoundarySetting.companion_id == companion_id)
        ).scalar_one_or_none()
        if not bs:
            bs = BoundarySetting(user_id=owner_id, companion_id=companion_id, **data)
            s.add(bs)
        else:
            for k, v in data.items():
                if v is not None and hasattr(bs, k):
                    setattr(bs, k, v)
            bs.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(bs)
        return bs


def _bs_dict(bs: BoundarySetting) -> dict:
    return {
        "id": str(bs.id),
        "user_id": str(bs.user_id),
        "companion_id": str(bs.companion_id),
        # Core conversation
        "memory_save_policy": bs.memory_save_policy,
        "sensitive_memory_policy": bs.sensitive_memory_policy,
        "proactive_level": bs.proactive_level,
        "notification_surface": bs.notification_surface,
        "allow_auto_memory_low_risk": bs.allow_auto_memory_low_risk,
        "allow_proactive_presence": bs.allow_proactive_presence,
        "allow_sensitive_memory_without_review": bs.allow_sensitive_memory_without_review,
        "suppressed_presence_types": bs.suppressed_presence_types or [],
        # Continuity
        "quiet_hours": bs.quiet_hours if bs.quiet_hours else {},
        "suppressed_presence_rules": bs.suppressed_presence_rules if isinstance(bs.suppressed_presence_rules, list) else [],
        "memory_confirmation_policy": bs.memory_confirmation_policy if bs.memory_confirmation_policy else {},
        "growth_confirmation_policy": bs.growth_confirmation_policy if bs.growth_confirmation_policy else {},
        "feedback_usage_policy": bs.feedback_usage_policy if bs.feedback_usage_policy else {},
        "continuity_visibility_policy": bs.continuity_visibility_policy if bs.continuity_visibility_policy else {},
        "max_presence_per_day": bs.max_presence_per_day,
        "min_presence_interval_minutes": bs.min_presence_interval_minutes,
        "meaningful_silence_enabled": bs.meaningful_silence_enabled,
    }
