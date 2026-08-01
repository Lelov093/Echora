"""Realtime compatibility resident presence service."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import (
    Companion,
    CompanionPresenceBudget,
    CompanionResidentStatusEvent,
    CoPresenceInvitation,
    FocusModeEvent,
    QuietHourSetting,
    ResidentPresenceEvent,
    User,
)
from app.services.realtime_copresence_service import get_session


def set_resident_status(user_id: uuid.UUID, companion_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        user = s.get(User, user_id)
        companion = s.get(Companion, companion_id)
        if user is None or companion is None or companion.user_id != user_id:
            return None
        status_type = payload.get("status_type") if payload.get("status_type") in {"available", "quiet", "focus", "sleep", "paused", "hard_stopped"} else "available"
        interruption_level = payload.get("interruption_level") if payload.get("interruption_level") in {"none", "low", "medium", "high"} else "low"
        allows_unsolicited = bool(payload.get("allows_unsolicited_presence", False)) and interruption_level in {"none", "low"}
        event = CompanionResidentStatusEvent(
            user_id=user_id,
            companion_id=companion_id,
            realtime_session_id=_to_uuid(payload.get("realtime_session_id")),
            status_type=status_type,
            status_source=payload.get("status_source") if payload.get("status_source") in {"user", "system", "schedule", "boundary_policy"} else "user",
            interruption_level=interruption_level,
            allows_unsolicited_presence=allows_unsolicited,
            presence_summary=payload.get("presence_summary"),
            policy_snapshot_json={"low_interruption_default": True, "unsolicited_presence_limited": True},
            occurred_at=_now(),
            metadata_={"implementation_origin": "resident_presence"},
        )
        s.add(event)
        s.add(
            ResidentPresenceEvent(
                user_id=user_id,
                companion_id=companion_id,
                realtime_session_id=_to_uuid(payload.get("realtime_session_id")),
                event_type="ambient_status",
                event_status="queued",
                interruption_level=interruption_level,
                requires_user_confirmation=interruption_level in {"medium", "high"},
                delivery_surface="app_page",
                event_summary=payload.get("presence_summary") or f"Resident status: {status_type}",
                policy_snapshot_json={"real_notifications_enabled": False},
                occurred_at=_now(),
                metadata_={"implementation_origin": "resident_presence"},
            )
        )
        s.commit()
        s.refresh(event)
        return _status_to_dict(event)


def evaluate_presence_budget(user_id: uuid.UUID, companion_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        companion = s.get(Companion, companion_id)
        if companion is None or companion.user_id != user_id:
            return None
        budget = s.execute(
            select(CompanionPresenceBudget)
            .where(
                CompanionPresenceBudget.user_id == user_id,
                CompanionPresenceBudget.companion_id == companion_id,
                CompanionPresenceBudget.budget_scope == "day",
                CompanionPresenceBudget.budget_status.in_(["active", "exhausted"]),
            )
            .order_by(CompanionPresenceBudget.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if budget is None:
            now = _now()
            budget = CompanionPresenceBudget(
                user_id=user_id,
                companion_id=companion_id,
                budget_scope="day",
                budget_status="active",
                enforcement_policy="queue_when_exhausted",
                max_presence_minutes=int(payload.get("max_presence_minutes") or 30),
                used_presence_minutes=0,
                max_interruptions=int(payload.get("max_interruptions") or 3),
                used_interruptions=0,
                window_starts_at=now,
                window_ends_at=now + timedelta(days=1),
                budget_policy_json={"resident_presence": "low_interruption"},
                metadata_={"implementation_origin": "resident_presence"},
            )
            s.add(budget)
            s.flush()
        requested_minutes = max(0, int(payload.get("presence_minutes") or 0))
        requested_interruptions = max(0, int(payload.get("interruptions") or 0))
        would_minutes = budget.used_presence_minutes + requested_minutes
        would_interruptions = budget.used_interruptions + requested_interruptions
        allowed = would_minutes <= budget.max_presence_minutes and would_interruptions <= budget.max_interruptions
        if allowed:
            budget.used_presence_minutes = would_minutes
            budget.used_interruptions = would_interruptions
            decision = "allowed"
        else:
            budget.budget_status = "exhausted"
            decision = budget.enforcement_policy
        s.commit()
        s.refresh(budget)
        return {**_budget_to_dict(budget), "decision": decision, "allowed": allowed}


def create_copresence_invitation(user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        target = s.get(Companion, _to_uuid(payload.get("target_companion_id")))
        if target is None or target.user_id != user_id:
            return None
        invitation = CoPresenceInvitation(
            user_id=user_id,
            co_presence_session_id=_to_uuid(payload.get("co_presence_session_id")),
            realtime_session_id=_to_uuid(payload.get("realtime_session_id")),
            inviter_companion_id=_to_uuid(payload.get("inviter_companion_id")),
            target_companion_id=target.id,
            invitation_status="queued",
            invitation_source=payload.get("invitation_source")
            if payload.get("invitation_source") in {"user_request", "companion_suggestion", "system"}
            else "user_request",
            requires_user_approval=True,
            auto_join_allowed=False,
            memory_candidate_allowed=False,
            invitation_reason=payload.get("invitation_reason"),
            policy_snapshot_json={"requires_user_approval": True, "auto_join_allowed": False},
            expires_at=_now() + timedelta(minutes=int(payload.get("ttl_minutes") or 30)),
            metadata_={"implementation_origin": "resident_presence"},
        )
        s.add(invitation)
        s.commit()
        s.refresh(invitation)
        return _invitation_to_dict(invitation)


def apply_meaningful_silence(user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        user = s.get(User, user_id)
        if user is None:
            return None
        companion_id = _to_uuid(payload.get("companion_id"))
        quiet = QuietHourSetting(
            user_id=user_id,
            companion_id=companion_id,
            quiet_status="active",
            quiet_policy="queue",
            day_of_week=payload.get("day_of_week"),
            start_minute=max(0, min(int(payload.get("start_minute") or 0), 1439)),
            end_minute=max(0, min(int(payload.get("end_minute") or 1439), 1439)),
            timezone=payload.get("timezone") or "UTC",
            allows_emergency_override=False,
            policy_json={"meaningful_silence": True},
            metadata_={"implementation_origin": "resident_presence"},
        )
        focus = FocusModeEvent(
            user_id=user_id,
            companion_id=companion_id,
            realtime_session_id=_to_uuid(payload.get("realtime_session_id")),
            focus_status="started",
            focus_scope=payload.get("focus_scope") if payload.get("focus_scope") in {"session", "channel", "companion", "all_realtime"} else "all_realtime",
            suppress_presence=True,
            suppress_notifications=True,
            allow_critical_only=True,
            reason=payload.get("reason") or "meaningful silence",
            started_at=_now(),
            policy_snapshot_json={"presence": "suppressed", "notifications": "suppressed"},
            metadata_={"implementation_origin": "resident_presence"},
        )
        s.add(quiet)
        s.add(focus)
        s.commit()
        s.refresh(quiet)
        s.refresh(focus)
        return {"quiet": _quiet_to_dict(quiet), "focus": _focus_to_dict(focus)}


def _status_to_dict(event: CompanionResidentStatusEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "user_id": str(event.user_id),
        "companion_id": str(event.companion_id),
        "realtime_session_id": str(event.realtime_session_id) if event.realtime_session_id else None,
        "status_type": event.status_type,
        "status_source": event.status_source,
        "interruption_level": event.interruption_level,
        "allows_unsolicited_presence": event.allows_unsolicited_presence,
        "presence_summary": event.presence_summary,
        "policy_snapshot_json": event.policy_snapshot_json or {},
        "occurred_at": event.occurred_at.isoformat() if event.occurred_at else None,
    }


def _budget_to_dict(budget: CompanionPresenceBudget) -> dict[str, Any]:
    return {
        "id": str(budget.id),
        "user_id": str(budget.user_id),
        "companion_id": str(budget.companion_id),
        "budget_scope": budget.budget_scope,
        "budget_status": budget.budget_status,
        "enforcement_policy": budget.enforcement_policy,
        "max_presence_minutes": budget.max_presence_minutes,
        "used_presence_minutes": budget.used_presence_minutes,
        "max_interruptions": budget.max_interruptions,
        "used_interruptions": budget.used_interruptions,
        "budget_policy_json": budget.budget_policy_json or {},
    }


def _invitation_to_dict(invitation: CoPresenceInvitation) -> dict[str, Any]:
    return {
        "id": str(invitation.id),
        "user_id": str(invitation.user_id),
        "realtime_session_id": str(invitation.realtime_session_id) if invitation.realtime_session_id else None,
        "inviter_companion_id": str(invitation.inviter_companion_id) if invitation.inviter_companion_id else None,
        "target_companion_id": str(invitation.target_companion_id) if invitation.target_companion_id else None,
        "invitation_status": invitation.invitation_status,
        "invitation_source": invitation.invitation_source,
        "requires_user_approval": invitation.requires_user_approval,
        "auto_join_allowed": invitation.auto_join_allowed,
        "memory_candidate_allowed": invitation.memory_candidate_allowed,
        "invitation_reason": invitation.invitation_reason,
        "policy_snapshot_json": invitation.policy_snapshot_json or {},
        "expires_at": invitation.expires_at.isoformat() if invitation.expires_at else None,
    }


def _quiet_to_dict(quiet: QuietHourSetting) -> dict[str, Any]:
    return {
        "id": str(quiet.id),
        "quiet_status": quiet.quiet_status,
        "quiet_policy": quiet.quiet_policy,
        "start_minute": quiet.start_minute,
        "end_minute": quiet.end_minute,
        "allows_emergency_override": quiet.allows_emergency_override,
        "policy_json": quiet.policy_json or {},
    }


def _focus_to_dict(focus: FocusModeEvent) -> dict[str, Any]:
    return {
        "id": str(focus.id),
        "focus_status": focus.focus_status,
        "focus_scope": focus.focus_scope,
        "suppress_presence": focus.suppress_presence,
        "suppress_notifications": focus.suppress_notifications,
        "allow_critical_only": focus.allow_critical_only,
        "reason": focus.reason,
    }


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _now() -> datetime:
    return datetime.now(timezone.utc)
