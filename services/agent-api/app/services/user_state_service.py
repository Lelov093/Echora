"""Continuous, low-risk EWMA user-state service."""

import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.algorithm_contract import clamp01
from app.core.config import settings
from app.db.models import FeedbackEvent
from app.db.models.user_state_snapshot import UserStateSnapshot

_engine = None
DEFAULT_RHO = 0.8
MIN_RHO = 0.7
MAX_RHO = 0.9
NEUTRAL_BASELINE = 0.5
VALUE_HALF_LIFE_DAYS = 30.0
CONFIDENCE_HALF_LIFE_DAYS = 14.0
SAFE_SIGNAL_TYPES = {
    "project_activity",
    "creative_activity",
    "interaction_acceptance",
    "focus_load",
    "presence_acceptance",
    "presence_dismissal",
    "memory_review_activity",
    "growth_review_activity",
    "continuity_need",
}


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def create_snapshot(data: dict) -> dict:
    """Persist one signal using a bounded, explainable EWMA update."""
    signal_type = str(data["signal_type"])
    if signal_type not in SAFE_SIGNAL_TYPES:
        raise ValueError(f"Unsupported or high-risk user-state signal: {signal_type}")
    now = _as_datetime(data.get("observation_window_end")) or datetime.now(timezone.utc)
    rho = max(MIN_RHO, min(MAX_RHO, float(data.get("smoothing_factor", DEFAULT_RHO))))
    observed = clamp01(data.get("observed_value"))
    observed_confidence = clamp01(data.get("confidence"), 0.5)
    event_count = max(1, int(data.get("source_event_count", 1)))
    uid = uuid.UUID(str(data["user_id"]))
    cid = uuid.UUID(str(data["companion_id"]))

    with get_session() as s:
        previous = _latest_snapshot(s, uid, cid, signal_type)
        previous_value, previous_confidence, age_days = _effective_previous(previous, now)
        smoothed = (rho * previous_value) + ((1.0 - rho) * observed)
        total_source_count = event_count + (previous.source_event_count if previous else 0)
        confidence = _combined_confidence(
            observed_confidence,
            previous_confidence,
            total_source_count,
        )
        state_json = {
            **(data.get("state_json") or {}),
            "event_type": "observation",
            "formula": "state_t = rho * state_(t-1) + (1-rho) * observed_signal_t",
            "raw_previous_value": previous.smoothed_value if previous else None,
            "effective_previous_value": round(previous_value, 4),
            "previous_confidence_after_decay": round(previous_confidence, 4),
            "previous_age_days": round(age_days, 4) if age_days is not None else None,
            "observed_confidence": round(observed_confidence, 4),
            "confidence_decay_half_life_days": CONFIDENCE_HALF_LIFE_DAYS,
            "value_decay_half_life_days": VALUE_HALF_LIFE_DAYS,
            "high_risk_action_eligible": confidence >= 0.7,
            "sensitive_inference": False,
        }
        row = _new_snapshot(
            data,
            user_id=uid,
            companion_id=cid,
            signal_type=signal_type,
            observed=observed,
            previous_value=previous_value if previous else None,
            smoothed=smoothed,
            rho=rho,
            confidence=confidence,
            source_event_count=total_source_count,
            now=now,
            state_json=state_json,
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return _uss_dict(row)


def override_state(
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    signal_type: str,
    value: float,
    *,
    reason: str,
    mode_key: str | None = None,
) -> dict:
    """Apply an explicit user override while retaining the previous value."""
    if signal_type not in SAFE_SIGNAL_TYPES:
        raise ValueError(f"Unsupported or high-risk user-state signal: {signal_type}")
    now = datetime.now(timezone.utc)
    value = clamp01(value)
    with get_session() as s:
        previous = _latest_snapshot(s, user_id, companion_id, signal_type)
        row = UserStateSnapshot(
            user_id=user_id,
            companion_id=companion_id,
            signal_type=signal_type,
            mode_key=mode_key,
            observed_value=value,
            previous_smoothed_value=previous.smoothed_value if previous else None,
            smoothed_value=value,
            smoothing_factor=0.0,
            confidence=1.0,
            source_event_count=(previous.source_event_count if previous else 0) + 1,
            observation_window_start=now,
            observation_window_end=now,
            reason=reason,
            state_json={
                "event_type": "user_override",
                "override_value": value,
                "previous_snapshot_id": str(previous.id) if previous else None,
                "high_risk_action_eligible": True,
                "sensitive_inference": False,
            },
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return _uss_dict(row)


def reset_state(
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    signal_type: str,
    *,
    reason: str,
    baseline: float = NEUTRAL_BASELINE,
    mode_key: str | None = None,
) -> dict:
    """Reset a signal to a neutral or explicitly supplied baseline."""
    result = override_state(
        user_id,
        companion_id,
        signal_type,
        clamp01(baseline, NEUTRAL_BASELINE),
        reason=reason,
        mode_key=mode_key,
    )
    with get_session() as s:
        row = s.get(UserStateSnapshot, uuid.UUID(result["id"]))
        state_json = dict(row.state_json or {})
        state_json["event_type"] = "reset"
        state_json["reset_baseline"] = row.smoothed_value
        row.state_json = state_json
        s.commit()
        s.refresh(row)
        return _uss_dict(row)


def get_current_state(
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return latest safe signals with confidence decayed to the read time."""
    now = now or datetime.now(timezone.utc)
    with get_session() as s:
        rows = list(
            s.execute(
                select(UserStateSnapshot)
                .where(
                    UserStateSnapshot.user_id == user_id,
                    UserStateSnapshot.companion_id == companion_id,
                    UserStateSnapshot.signal_type.in_(SAFE_SIGNAL_TYPES),
                )
                .order_by(UserStateSnapshot.created_at.desc())
            ).scalars().all()
        )
    latest: dict[str, UserStateSnapshot] = {}
    for row in rows:
        latest.setdefault(row.signal_type, row)
    signals = {}
    for signal_type, row in latest.items():
        value, confidence, age_days = _effective_previous(row, now)
        signals[signal_type] = {
            "value": round(value, 4),
            "confidence": round(confidence, 4),
            "source_event_count": row.source_event_count,
            "snapshot_id": str(row.id),
            "age_days": round(age_days or 0.0, 4),
            "high_risk_action_eligible": confidence >= 0.7,
        }
    return {
        "user_id": str(user_id),
        "companion_id": str(companion_id),
        "signals": signals,
        "sensitive_inference": False,
        "generated_at": now.isoformat(),
    }


def observe_interaction_acceptance(companion_id: uuid.UUID, *, lookback_days: int = 30) -> dict:
    """Build an explicit-feedback-only acceptance observation."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)
    positive_actions = {"accept", "confirm", "helpful", "accept_presence", "continued", "useful"}
    negative_actions = {"reject", "dismiss", "ignored", "disabled", "suppress_type", "too_intrusive"}
    with get_session() as s:
        events = list(
            s.execute(
                select(FeedbackEvent).where(
                    FeedbackEvent.companion_id == companion_id,
                    FeedbackEvent.feedback_source == "explicit",
                    FeedbackEvent.created_at >= cutoff,
                    FeedbackEvent.deleted_at.is_(None),
                )
            ).scalars().all()
        )
    relevant = [event for event in events if event.action in positive_actions | negative_actions]
    positives = sum(1 for event in relevant if event.action in positive_actions)
    negatives = len(relevant) - positives
    observed = (positives + 1.0) / (positives + negatives + 2.0)
    confidence = min(0.9, 0.3 + (0.08 * len(relevant)))
    return {
        "observed_value": round(observed, 4),
        "confidence": round(confidence, 4),
        "source_event_count": max(1, len(relevant)),
        "source_feedback_event_ids": [str(event.id) for event in relevant],
        "positive_count": positives,
        "negative_count": negatives,
        "explicit_only": True,
    }


def list_snapshots(
    user_id: uuid.UUID | None = None,
    companion_id: uuid.UUID | None = None,
    signal_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    with get_session() as s:
        stmt = select(UserStateSnapshot)
        if user_id:
            stmt = stmt.where(UserStateSnapshot.user_id == user_id)
        if companion_id:
            stmt = stmt.where(UserStateSnapshot.companion_id == companion_id)
        if signal_type:
            stmt = stmt.where(UserStateSnapshot.signal_type == signal_type)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(UserStateSnapshot.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = [_uss_dict(uss) for uss in s.execute(stmt).scalars().all()]
        return {"items": items, "total": total}


def get_snapshot(snapshot_id: uuid.UUID) -> dict | None:
    with get_session() as s:
        uss = s.get(UserStateSnapshot, snapshot_id)
        return _uss_dict(uss) if uss else None


def list_for_user(user_id: uuid.UUID, page: int = 1, page_size: int = 20) -> dict:
    return list_snapshots(user_id=user_id, page=page, page_size=page_size)


def _latest_snapshot(
    session: Session,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    signal_type: str,
) -> UserStateSnapshot | None:
    return session.execute(
        select(UserStateSnapshot)
        .where(
            UserStateSnapshot.user_id == user_id,
            UserStateSnapshot.companion_id == companion_id,
            UserStateSnapshot.signal_type == signal_type,
        )
        .order_by(UserStateSnapshot.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _effective_previous(
    previous: UserStateSnapshot | None,
    now: datetime,
) -> tuple[float, float, float | None]:
    if previous is None:
        return NEUTRAL_BASELINE, 0.0, None
    created_at = _as_utc(previous.created_at)
    age_days = max(0.0, (now - created_at).total_seconds() / 86400.0)
    value_decay = math.pow(0.5, age_days / VALUE_HALF_LIFE_DAYS)
    confidence_decay = math.pow(0.5, age_days / CONFIDENCE_HALF_LIFE_DAYS)
    value = NEUTRAL_BASELINE + ((previous.smoothed_value - NEUTRAL_BASELINE) * value_decay)
    confidence = previous.confidence * confidence_decay
    return clamp01(value, NEUTRAL_BASELINE), clamp01(confidence), age_days


def _combined_confidence(observed: float, previous: float, source_count: int) -> float:
    if previous <= 0:
        combined = observed
    else:
        combined = (0.65 * observed) + (0.35 * previous)
    sample_bonus = min(0.15, math.log1p(max(1, source_count)) * 0.035)
    return clamp01(min(0.95, combined + sample_bonus))


def _new_snapshot(
    data: dict,
    *,
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    signal_type: str,
    observed: float,
    previous_value: float | None,
    smoothed: float,
    rho: float,
    confidence: float,
    source_event_count: int,
    now: datetime,
    state_json: dict,
) -> UserStateSnapshot:
    return UserStateSnapshot(
        user_id=user_id,
        companion_id=companion_id,
        conversation_id=_as_uuid(data.get("conversation_id")),
        trace_run_id=_as_uuid(data.get("trace_run_id")),
        signal_type=signal_type,
        mode_key=data.get("mode_key"),
        observed_value=round(observed, 4),
        previous_smoothed_value=round(previous_value, 4) if previous_value is not None else None,
        smoothed_value=round(clamp01(smoothed), 4),
        smoothing_factor=round(rho, 4),
        confidence=round(confidence, 4),
        source_event_count=source_event_count,
        observation_window_start=_as_datetime(data.get("observation_window_start")) or now,
        observation_window_end=now,
        reason=data.get("reason"),
        source_feedback_event_ids=[
            uuid.UUID(str(value)) for value in data.get("source_feedback_event_ids", [])
        ],
        source_trace_run_ids=[
            uuid.UUID(str(value)) for value in data.get("source_trace_run_ids", [])
        ],
        state_json=state_json,
    )


def _uss_dict(uss: UserStateSnapshot) -> dict:
    return {
        "id": str(uss.id),
        "user_id": str(uss.user_id),
        "companion_id": str(uss.companion_id),
        "conversation_id": str(uss.conversation_id) if uss.conversation_id else None,
        "trace_run_id": str(uss.trace_run_id) if uss.trace_run_id else None,
        "signal_type": uss.signal_type,
        "mode_key": uss.mode_key,
        "observed_value": uss.observed_value,
        "previous_smoothed_value": uss.previous_smoothed_value,
        "smoothed_value": uss.smoothed_value,
        "smoothing_factor": uss.smoothing_factor,
        "confidence": uss.confidence,
        "source_event_count": uss.source_event_count,
        "observation_window_start": uss.observation_window_start.isoformat() if uss.observation_window_start else None,
        "observation_window_end": uss.observation_window_end.isoformat() if uss.observation_window_end else None,
        "reason": uss.reason,
        "source_feedback_event_ids": [str(fid) for fid in (uss.source_feedback_event_ids or [])],
        "source_trace_run_ids": [str(tid) for tid in (uss.source_trace_run_ids or [])],
        "state_json": uss.state_json or {},
        "created_at": uss.created_at.isoformat() if uss.created_at else None,
    }


def _as_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _as_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return _as_utc(value)
    return _as_utc(datetime.fromisoformat(str(value)))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
