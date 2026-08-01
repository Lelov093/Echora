"""Presence Opportunity service layer."""

import uuid
import math
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import create_engine, func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    CompanionIdentityProfile,
    CompanionBoundaryProfile,
    CompanionPresenceBudget,
    CompanionResidentStatusEvent,
    FeedbackEvent,
    FocusModeEvent,
    PresenceOpportunity,
    QuietHourSetting,
    ScopedHardStopEvent,
    BoundarySetting,
)

_engine = None
_COMPAT_PRESENCE_TYPE_KEY = "phase4_type"
_COMPAT_PRESENCE_SURFACE_KEY = "phase4_surface"


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def _record_presence_feedback(
    opportunity: PresenceOpportunity,
    action: str,
    *,
    reward: float,
    feedback_source: str = "explicit",
) -> dict:
    from app.services.feedback_service import create_feedback_event

    feedback = create_feedback_event(
        {
            "user_id": str(opportunity.user_id),
            "companion_id": str(opportunity.companion_id),
            "conversation_id": str(opportunity.conversation_id) if opportunity.conversation_id else None,
            "target_type": "presence_opportunity",
            "target_id": str(opportunity.id),
            "action": action,
            "reward": reward,
            "feedback_source": feedback_source,
            "idempotency_key": f"presence:{opportunity.id}:{action}",
            "sample_provenance": {"source_service": "presence_service"},
            "context_json": {
                "opportunity_type": opportunity.type,
                "recommended_surface": opportunity.recommended_surface,
                "opportunity_context_hash": opportunity.opportunity_context_hash,
            },
            "algorithm_key": "presence",
            "effect_already_applied": True,
        }
    )
    try:
        from app.services.strategy_service import create_presence_feedback_sample

        create_presence_feedback_sample(
            {
                "user_id": str(opportunity.user_id),
                "companion_id": str(opportunity.companion_id),
                "presence_opportunity_id": str(opportunity.id),
                "feedback_event_id": feedback["id"],
                "action_taken": _surface_action(opportunity.recommended_surface),
                "reward": reward,
                "feature_json": {
                    "opportunity_type": _effective_type(opportunity),
                    "surface": _effective_surface(opportunity),
                    "interruption_risk": float(opportunity.interruption_risk or 0.0),
                    "feedback_action": action,
                },
            }
        )
    except Exception:
        pass
    return feedback


def _link_feedback(session: Session, opportunity: PresenceOpportunity, feedback: dict) -> None:
    opportunity.feedback_event_id = uuid.UUID(feedback["id"])
    opportunity.feedback_label = feedback["label"]
    session.commit()
    session.refresh(opportunity)


def get_presence_feedback_profile(
    companion_id: uuid.UUID,
    opportunity_type: str,
    surface: str,
    *,
    lookback_days: int = 90,
    now: datetime | None = None,
) -> dict:
    """Return an isolated, explicit-feedback-only calibration profile."""
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(days=lookback_days)
    positive = 0.0
    negative = 0.0
    dismissal_weight = 0.0
    explicit_signals = 0

    with get_session() as s:
        opportunities = list(
            s.execute(
                select(PresenceOpportunity).where(
                    PresenceOpportunity.companion_id == companion_id,
                    PresenceOpportunity.created_at >= cutoff,
                )
            ).scalars().all()
        )
        matching = [
            item
            for item in opportunities
            if _effective_type(item) == opportunity_type and _effective_surface(item) == surface
        ]
        ids = [item.id for item in matching]
        feedback = []
        if ids:
            feedback = list(
                s.execute(
                    select(FeedbackEvent).where(
                        FeedbackEvent.companion_id == companion_id,
                        FeedbackEvent.target_type == "presence_opportunity",
                        FeedbackEvent.target_id.in_(ids),
                        FeedbackEvent.deleted_at.is_(None),
                    )
                ).scalars().all()
            )

    by_target = {item.target_id: item for item in feedback}
    for opportunity in matching:
        event = by_target.get(opportunity.id)
        signal = _presence_signal(opportunity, event)
        if signal is None:
            continue
        explicit_signals += 1
        if signal in {"accepted", "continued"}:
            positive += 1.0
        elif signal in {"ignored", "dismissed", "disabled"}:
            negative += 1.0
        if signal in {"dismissed", "disabled"}:
            occurred_at = opportunity.dismissed_at or (event.created_at if event else opportunity.updated_at)
            age_days = max(0.0, (now - _as_utc(occurred_at)).total_seconds() / 86400.0)
            dismissal_weight += math.exp(-age_days / 14.0)

    acceptance_rate = (positive + 1.0) / (positive + negative + 2.0)
    dismissal_penalty = min(1.0, dismissal_weight / 2.0)
    return {
        "companion_id": str(companion_id),
        "opportunity_type": opportunity_type,
        "surface": surface,
        "acceptance_rate": round(acceptance_rate, 4),
        "recent_dismissal_penalty": round(dismissal_penalty, 4),
        "positive_signals": positive,
        "negative_signals": negative,
        "explicit_signals": explicit_signals,
        "unshown_counted_as_ignored": False,
        "policy_mode": "heuristic",
    }


def evaluate_presence_suppression(
    user_id: uuid.UUID,
    companion_id: uuid.UUID,
    opportunity_type: str,
    *,
    min_interval_seconds: int = 1800,
    realtime_session_id: uuid.UUID | None = None,
    now: datetime | None = None,
) -> dict:
    """Apply hard-stop, silence, budget, and interval gates in precedence order."""
    now = now or datetime.now(timezone.utc)
    scope_predicates = [
        ScopedHardStopEvent.hard_stop_scope == "all_realtime",
        (
            (ScopedHardStopEvent.hard_stop_scope == "companion")
            & (ScopedHardStopEvent.companion_id == companion_id)
        ),
    ]
    if realtime_session_id is not None:
        scope_predicates.append(
            (ScopedHardStopEvent.hard_stop_scope == "session")
            & (ScopedHardStopEvent.realtime_session_id == realtime_session_id)
        )

    with get_session() as s:
        profile_status = s.execute(
            select(CompanionIdentityProfile.profile_status).where(
                CompanionIdentityProfile.companion_id == companion_id
            )
        ).scalar_one_or_none()
        if profile_status == "archived":
            return _suppression("companion_archived", hard_block=True)

        boundary_setting = s.execute(
            select(BoundarySetting).where(
                BoundarySetting.user_id == user_id,
                BoundarySetting.companion_id == companion_id,
            )
        ).scalar_one_or_none()
        if boundary_setting is not None:
            if not boundary_setting.allow_proactive_presence:
                return _suppression("proactive_presence_disabled", hard_block=True, event_id=boundary_setting.id)
            if opportunity_type in set(boundary_setting.suppressed_presence_types or []):
                return _suppression("presence_type_suppressed", hard_block=True, event_id=boundary_setting.id)
            if _json_quiet_active(boundary_setting.quiet_hours or {}, now):
                return _suppression("boundary_quiet_hours", event_id=boundary_setting.id)

        boundary_profile = s.execute(
            select(CompanionBoundaryProfile).where(
                CompanionBoundaryProfile.user_id == user_id,
                CompanionBoundaryProfile.companion_id == companion_id,
            )
        ).scalar_one_or_none()
        if boundary_profile is not None:
            interrupt_policy = str(boundary_profile.presence_interrupt_policy or "")
            if interrupt_policy in {"user_initiated_only", "silent_only"}:
                return _suppression(f"interrupt_policy_{interrupt_policy}", hard_block=True, event_id=boundary_profile.id)
            profile_quiet = (boundary_profile.boundary_json or {}).get("quiet_hours") or {}
            if _json_quiet_active(profile_quiet, now):
                return _suppression("profile_quiet_hours", event_id=boundary_profile.id)

        hard_stop = s.execute(
            select(ScopedHardStopEvent)
            .where(
                ScopedHardStopEvent.user_id == user_id,
                ScopedHardStopEvent.hard_stop_status == "active",
                ScopedHardStopEvent.released_at.is_(None),
                or_(*scope_predicates),
            )
            .order_by(ScopedHardStopEvent.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if hard_stop is not None:
            return _suppression("hard_stop", hard_block=True, event_id=hard_stop.id)

        resident = s.execute(
            select(CompanionResidentStatusEvent)
            .where(
                CompanionResidentStatusEvent.user_id == user_id,
                CompanionResidentStatusEvent.companion_id == companion_id,
            )
            .order_by(CompanionResidentStatusEvent.occurred_at.desc(), CompanionResidentStatusEvent.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if resident is not None and resident.status_type in {"hard_stopped", "paused"}:
            return _suppression(f"resident_{resident.status_type}", hard_block=True, event_id=resident.id)

        focus = s.execute(
            select(FocusModeEvent)
            .where(
                FocusModeEvent.user_id == user_id,
                FocusModeEvent.focus_status.in_(["active", "started"]),
                FocusModeEvent.suppress_presence.is_(True),
                or_(FocusModeEvent.companion_id.is_(None), FocusModeEvent.companion_id == companion_id),
                FocusModeEvent.ended_at.is_(None),
            )
            .order_by(FocusModeEvent.started_at.desc(), FocusModeEvent.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if focus is not None:
            return _suppression("focus_mode", event_id=focus.id)

        quiet_settings = list(
            s.execute(
                select(QuietHourSetting).where(
                    QuietHourSetting.user_id == user_id,
                    QuietHourSetting.quiet_status == "active",
                    or_(QuietHourSetting.companion_id.is_(None), QuietHourSetting.companion_id == companion_id),
                )
            ).scalars().all()
        )
        for quiet in quiet_settings:
            if _quiet_active(quiet, now):
                return _suppression("quiet_hours", event_id=quiet.id)

        if boundary_setting is not None and (boundary_setting.max_presence_per_day or 0) > 0:
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            delivered_today = s.execute(
                select(func.count()).select_from(PresenceOpportunity).where(
                    PresenceOpportunity.user_id == user_id,
                    PresenceOpportunity.companion_id == companion_id,
                    PresenceOpportunity.status == "accepted",
                    PresenceOpportunity.created_at >= start_of_day,
                )
            ).scalar() or 0
            if delivered_today >= boundary_setting.max_presence_per_day:
                return _suppression("daily_presence_limit", event_id=boundary_setting.id)

        budget = s.execute(
            select(CompanionPresenceBudget)
            .where(
                CompanionPresenceBudget.user_id == user_id,
                CompanionPresenceBudget.companion_id == companion_id,
                CompanionPresenceBudget.budget_status.in_(["active", "exhausted"]),
                or_(CompanionPresenceBudget.window_ends_at.is_(None), CompanionPresenceBudget.window_ends_at >= now),
            )
            .order_by(CompanionPresenceBudget.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if budget is not None and (
            budget.budget_status == "exhausted"
            or budget.used_presence_minutes >= budget.max_presence_minutes
            or budget.used_interruptions >= budget.max_interruptions
        ):
            return _suppression("presence_budget", event_id=budget.id)

        configured_interval = (
            max(0, int(boundary_setting.min_presence_interval_minutes or 0)) * 60
            if boundary_setting is not None
            else 0
        )
        effective_interval = max(min_interval_seconds, configured_interval)
        if effective_interval > 0:
            last_visible = s.execute(
                select(PresenceOpportunity)
                .where(
                    PresenceOpportunity.companion_id == companion_id,
                    PresenceOpportunity.type == opportunity_type,
                    PresenceOpportunity.status.in_(["queued", "shown", "accepted"]),
                )
                .order_by(PresenceOpportunity.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if last_visible is not None:
                elapsed = (now - _as_utc(last_visible.created_at)).total_seconds()
                if elapsed < effective_interval:
                    return _suppression(
                        "min_interval",
                        event_id=last_visible.id,
                        retry_after_seconds=max(0, int(effective_interval - elapsed)),
                    )

    return {
        "suppress": False,
        "hard_block": False,
        "reason": None,
        "decision": "eligible",
        "opportunity_type": opportunity_type,
    }


def record_opportunity_signal(opportunity_id: uuid.UUID, signal: str) -> PresenceOpportunity | None:
    """Record explicit lifecycle signals; queued rows are never inferred as ignored."""
    reward_by_signal = {
        "shown": 0.0,
        "continued": 0.8,
        "ignored": -0.3,
        "disabled": -1.0,
    }
    if signal not in reward_by_signal:
        raise ValueError(f"Unsupported presence signal: {signal}")
    with get_session() as s:
        opportunity = s.get(PresenceOpportunity, opportunity_id)
        if opportunity is None:
            return None
        opportunity.status = signal
        opportunity.user_action = signal
        opportunity.reward = reward_by_signal[signal]
        opportunity.updated_at = datetime.now(timezone.utc)
        if signal == "disabled":
            opportunity.dismissed_at = opportunity.updated_at
        s.commit()
        s.refresh(opportunity)
        feedback = _record_presence_feedback(
            opportunity,
            signal,
            reward=reward_by_signal[signal],
            feedback_source="explicit",
        )
        _link_feedback(s, opportunity, feedback)
        return opportunity


def list_opportunities(companion_id: uuid.UUID | None = None, status: str | None = None,
                       type_: str | None = None, page: int = 1, page_size: int = 20) -> dict:
    with get_session() as s:
        stmt = select(PresenceOpportunity)
        if companion_id:
            stmt = stmt.where(PresenceOpportunity.companion_id == companion_id)
        if status:
            stmt = stmt.where(PresenceOpportunity.status == status)
        if type_:
            stmt = stmt.where(PresenceOpportunity.type == type_)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(PresenceOpportunity.priority.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def get_opportunity(opportunity_id: uuid.UUID) -> PresenceOpportunity | None:
    with get_session() as s:
        return s.get(PresenceOpportunity, opportunity_id)


def accept_opportunity(opportunity_id: uuid.UUID, conversation_id: uuid.UUID | None = None) -> dict | None:
    with get_session() as s:
        o = s.get(PresenceOpportunity, opportunity_id)
        if not o:
            return None
        o.status = "accepted"
        o.user_action = "accepted"
        o.reward = 1.0
        o.accepted_at = datetime.now(timezone.utc)
        o.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(o)
        feedback = _record_presence_feedback(o, "accept_presence", reward=1.0)
        _link_feedback(s, o, feedback)
        return {"opportunity": _opp_dict(o), "next": {"conversation_id": str(conversation_id) if conversation_id else None}}


def dismiss_opportunity(opportunity_id: uuid.UUID) -> PresenceOpportunity | None:
    with get_session() as s:
        o = s.get(PresenceOpportunity, opportunity_id)
        if not o:
            return None
        o.status = "dismissed"
        o.user_action = "dismissed"
        o.reward = -0.8
        o.dismissed_at = datetime.now(timezone.utc)
        o.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(o)
        feedback = _record_presence_feedback(o, "dismiss", reward=-0.8)
        _link_feedback(s, o, feedback)
        return o


def snooze_opportunity(opportunity_id: uuid.UUID, snoozed_until: datetime | None = None) -> PresenceOpportunity | None:
    with get_session() as s:
        o = s.get(PresenceOpportunity, opportunity_id)
        if not o:
            return None
        o.status = "snoozed"
        o.snoozed_until = snoozed_until or datetime.now(timezone.utc)
        o.updated_at = datetime.now(timezone.utc)
        s.commit()
        s.refresh(o)
        feedback = _record_presence_feedback(o, "snooze", reward=-0.25)
        _link_feedback(s, o, feedback)
        return o


def suppress_opportunity_type(opportunity_id: uuid.UUID) -> PresenceOpportunity | None:
    """Suppress this opportunity and record type in boundary_settings for future blocking."""
    with get_session() as s:
        o = s.get(PresenceOpportunity, opportunity_id)
        if not o:
            return None
        o.status = "suppressed"
        o.user_action = "suppressed"
        o.updated_at = datetime.now(timezone.utc)

        # Also write to boundary_settings to suppress future opportunities of this type
        try:
            from app.db.models.settings import BoundarySetting
            bs = s.query(BoundarySetting).filter(
                BoundarySetting.companion_id == o.companion_id
            ).first()
            if bs:
                stypes = list(bs.suppressed_presence_types or [])
                if o.type not in stypes:
                    stypes.append(o.type)
                    bs.suppressed_presence_types = stypes
                    bs.updated_at = datetime.now(timezone.utc)
        except Exception:
            pass

        s.commit()
        s.refresh(o)
        feedback = _record_presence_feedback(o, "suppress_type", reward=-1.0)
        _link_feedback(s, o, feedback)
        return o


def _opp_dict(o: PresenceOpportunity) -> dict:
    return {
        "id": str(o.id), "type": o.type, "title": o.title, "message": o.message,
        "reason": o.reason, "priority": o.priority,
        "recommended_surface": o.recommended_surface, "status": o.status,
        "created_at": o.created_at.isoformat() if o.created_at else None,
    }


def _presence_signal(opportunity: PresenceOpportunity, event: FeedbackEvent | None) -> str | None:
    action = (event.action if event else opportunity.user_action or "").lower()
    status = (opportunity.status or "").lower()
    if action in {"accept_presence", "accept", "accepted"} or status == "accepted":
        return "accepted"
    if action in {"continued", "continue"} or status == "continued":
        return "continued"
    if action in {"ignored", "ignore"} or status == "ignored":
        return "ignored"
    if action in {"dismiss", "dismissed"} or status == "dismissed":
        return "dismissed"
    if action in {"disabled", "suppress_type", "disable"} or status in {"disabled", "suppressed"}:
        return "disabled"
    if action == "shown" or status == "shown":
        return "shown"
    return None


def _effective_type(opportunity: PresenceOpportunity) -> str:
    calibration = opportunity.calibration_json or {}
    return str(
        calibration.get("presence_type")
        or calibration.get(_COMPAT_PRESENCE_TYPE_KEY)
        or opportunity.type
    )


def _effective_surface(opportunity: PresenceOpportunity) -> str:
    calibration = opportunity.calibration_json or {}
    return str(
        calibration.get("presence_surface")
        or calibration.get(_COMPAT_PRESENCE_SURFACE_KEY)
        or opportunity.recommended_surface
    )


def _surface_action(surface: str) -> str:
    return {
        "silent": "silence",
        "none": "no_show",
        "hub": "hub",
        "inline": "hub",
        "scene_panel": "hub",
        "session_surface": "hub",
        "queue": "queue",
        "hub_queue": "queue",
    }.get(str(surface), "queue")


def _quiet_active(setting: QuietHourSetting, now: datetime) -> bool:
    try:
        local_now = now.astimezone(ZoneInfo(setting.timezone or "UTC"))
    except ZoneInfoNotFoundError:
        local_now = now.astimezone(timezone.utc)
    if setting.day_of_week is not None and setting.day_of_week != local_now.weekday():
        return False
    minute = (local_now.hour * 60) + local_now.minute
    if setting.start_minute <= setting.end_minute:
        return setting.start_minute <= minute <= setting.end_minute
    return minute >= setting.start_minute or minute <= setting.end_minute


def _json_quiet_active(value: dict, now: datetime) -> bool:
    """Evaluate the owner/profile quiet-hours JSON without weakening invalid values."""
    if not isinstance(value, dict) or not value or value.get("enabled") is False:
        return False
    start = value.get("start") or value.get("start_time")
    end = value.get("end") or value.get("end_time")
    if not isinstance(start, str) or not isinstance(end, str):
        return False
    try:
        zone = ZoneInfo(str(value.get("timezone") or "UTC"))
        local_now = now.astimezone(zone)
        start_hour, start_minute = (int(part) for part in start.split(":", 1))
        end_hour, end_minute = (int(part) for part in end.split(":", 1))
        start_value = start_hour * 60 + start_minute
        end_value = end_hour * 60 + end_minute
        if not (0 <= start_value <= 1439 and 0 <= end_value <= 1439):
            return True
    except (TypeError, ValueError, ZoneInfoNotFoundError):
        return True
    weekdays = value.get("weekdays")
    if isinstance(weekdays, list) and weekdays and local_now.weekday() not in weekdays:
        return False
    minute = local_now.hour * 60 + local_now.minute
    if start_value <= end_value:
        return start_value <= minute <= end_value
    return minute >= start_value or minute <= end_value


def _suppression(reason: str, *, hard_block: bool = False, event_id=None, **extra) -> dict:
    return {
        "suppress": True,
        "hard_block": hard_block,
        "reason": reason,
        "decision": "blocked" if hard_block else "meaningful_silence",
        "event_id": str(event_id) if event_id else None,
        **extra,
    }


def _as_utc(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
