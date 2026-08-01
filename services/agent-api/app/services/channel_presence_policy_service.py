"""Channel Gateway channel presence policy and check-in scheduler service."""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    ChannelBinding,
    ChannelCheckinSetting,
    ChannelFocusModeRule,
    ChannelMeaningfulSilenceEvent,
    ChannelOutboundSuppressionEvent,
    ChannelPresenceBudgetEvent,
    ChannelPresencePolicy,
    ChannelQuietHourRule,
)

_engine = None
_SENSITIVE_KEY_PARTS = ("token", "secret", "password", "api_key", "authorization", "credential", "raw")
_SILENCE_REASON_VALUES = {"low_salience", "recent_user_activity", "relationship_boundary", "cooldown", "manual"}
_SILENCE_REASON_ALIASES = {
    "user_busy": "recent_user_activity",
    "busy": "recent_user_activity",
    "recent_activity": "recent_user_activity",
    "boundary": "relationship_boundary",
}


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def list_policies(
    *,
    channel_binding_id: uuid.UUID | None = None,
    companion_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(ChannelPresencePolicy)
        if channel_binding_id is not None:
            stmt = stmt.where(ChannelPresencePolicy.channel_binding_id == channel_binding_id)
        if companion_id is not None:
            stmt = stmt.where(ChannelPresencePolicy.companion_id == companion_id)
        if status:
            stmt = stmt.where(ChannelPresencePolicy.policy_status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = list(
            s.execute(
                stmt.order_by(ChannelPresencePolicy.updated_at.desc(), ChannelPresencePolicy.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
        )
        return {"items": [_policy_bundle(s, item) for item in items], "total": total}


def create_policy(payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        binding = s.get(ChannelBinding, _to_uuid(payload.get("channel_binding_id")))
        if binding is None:
            return None
        policy = ChannelPresencePolicy(
            user_id=binding.user_id,
            companion_id=binding.companion_id,
            channel_binding_id=binding.id,
            provider_id=binding.provider_id,
            provider_bot_id=binding.provider_bot_id,
            policy_status=payload.get("policy_status") or "draft",
            presence_mode="reply_only",
            reply_only_default=True,
            low_frequency_checkin_enabled=False,
            channel_mute=bool(payload.get("channel_mute", False)),
            outbound_disabled=bool(payload.get("outbound_disabled", False)),
            daily_presence_budget=0,
            remaining_presence_budget=0,
            quiet_hours_enforced=True,
            focus_mode_enforced=True,
            meaningful_silence_enforced=True,
            policy_json=_safe_json(payload.get("policy_json")),
            metadata_={"implementation_origin": "channel_presence"},
        )
        s.add(policy)
        s.flush()
        setting = ChannelCheckinSetting(
            channel_presence_policy_id=policy.id,
            enabled=False,
            frequency="manual",
            min_interval_seconds=86400,
            requires_user_opt_in=True,
            quiet_hours_enforced=True,
            focus_mode_enforced=True,
            presence_budget_enforced=True,
            meaningful_silence_enforced=True,
            settings_json={"opt_in": False},
            metadata_={"implementation_origin": "channel_presence"},
        )
        s.add(setting)
        s.commit()
        s.refresh(policy)
        return _policy_bundle(s, policy)


def patch_policy(policy_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        policy = s.get(ChannelPresencePolicy, policy_id)
        if policy is None:
            return None
        for field in ["policy_status", "channel_mute", "outbound_disabled"]:
            if field in payload and payload[field] is not None:
                setattr(policy, field, payload[field])
        if "remaining_presence_budget" in payload:
            policy.remaining_presence_budget = max(0, int(payload["remaining_presence_budget"]))
        if "daily_presence_budget" in payload:
            policy.daily_presence_budget = max(0, int(payload["daily_presence_budget"]))
        if isinstance(payload.get("policy_json"), dict):
            policy.policy_json = _safe_json(payload["policy_json"])
        if isinstance(payload.get("focus_mode"), dict):
            _upsert_focus_rule(s, policy.id, payload["focus_mode"])
        if isinstance(payload.get("quiet_hours"), dict):
            _upsert_quiet_rule(s, policy.id, payload["quiet_hours"])
        policy.reply_only_default = True
        policy.quiet_hours_enforced = True
        policy.focus_mode_enforced = True
        policy.meaningful_silence_enforced = True
        policy.updated_at = _now()
        s.commit()
        s.refresh(policy)
        return _policy_bundle(s, policy)


def enable_checkin(policy_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    if not payload.get("user_opt_in"):
        return None
    with get_session() as s:
        policy = s.get(ChannelPresencePolicy, policy_id)
        if policy is None:
            return None
        policy.policy_status = "active"
        policy.presence_mode = "low_frequency_checkin"
        policy.reply_only_default = True
        policy.low_frequency_checkin_enabled = True
        policy.daily_presence_budget = max(0, int(payload.get("daily_presence_budget", 1)))
        policy.remaining_presence_budget = max(0, int(payload.get("remaining_presence_budget", policy.daily_presence_budget)))
        policy.quiet_hours_enforced = True
        policy.focus_mode_enforced = True
        policy.meaningful_silence_enforced = True
        policy.updated_at = _now()

        setting = _get_checkin_setting(s, policy.id)
        if setting is None:
            setting = ChannelCheckinSetting(channel_presence_policy_id=policy.id)
            s.add(setting)
        setting.enabled = True
        setting.frequency = payload.get("frequency") or "daily"
        setting.min_interval_seconds = max(0, int(payload.get("min_interval_seconds", 86400)))
        setting.requires_user_opt_in = True
        setting.quiet_hours_enforced = True
        setting.focus_mode_enforced = True
        setting.presence_budget_enforced = True
        setting.meaningful_silence_enforced = True
        setting.next_eligible_at = _now()
        setting.settings_json = {"opt_in": True, **_safe_json(payload.get("settings_json"))}
        setting.updated_at = _now()
        _record_budget_event(s, policy, "allocated", policy.daily_presence_budget, "Check-in budget allocated")
        s.commit()
        s.refresh(policy)
        return _policy_bundle(s, policy)


def evaluate_checkin(payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        policy = s.get(ChannelPresencePolicy, _to_uuid(payload.get("channel_presence_policy_id")))
        if policy is None:
            return None
        setting = _get_checkin_setting(s, policy.id)
        reason = _suppression_reason(s, policy, setting, payload)
        if reason:
            suppression = _record_suppression(s, policy, reason, f"Check-in suppressed by {reason}")
            _record_budget_event(s, policy, "suppressed", 0, f"Check-in suppressed by {reason}")
            if reason == "meaningful_silence":
                _record_meaningful_silence(s, policy, payload)
            s.commit()
            s.refresh(policy)
            return {
                "decision": "suppressed",
                "suppression_reason": reason,
                "suppression_event": _suppression_to_dict(suppression),
                "policy": _policy_to_dict(policy),
            }

        policy.remaining_presence_budget = max(0, policy.remaining_presence_budget - 1)
        policy.updated_at = _now()
        setting.next_eligible_at = _now() + timedelta(seconds=max(0, setting.min_interval_seconds))
        setting.updated_at = _now()
        budget = _record_budget_event(s, policy, "consumed", -1, "Low-frequency check-in budget consumed")
        s.commit()
        s.refresh(policy)
        s.refresh(budget)
        return {
            "decision": "eligible",
            "suppression_reason": None,
            "budget_event": _budget_event_to_dict(budget),
            "policy": _policy_to_dict(policy),
            "delivery_intent": {
                "channel_binding_id": str(policy.channel_binding_id),
                "provider_bot_id": str(policy.provider_bot_id) if policy.provider_bot_id else None,
                "real_provider_send": False,
            },
        }


def _suppression_reason(
    s: Session,
    policy: ChannelPresencePolicy,
    setting: ChannelCheckinSetting | None,
    payload: dict[str, Any],
) -> str | None:
    binding = s.get(ChannelBinding, policy.channel_binding_id)
    if binding is None or binding.binding_status in {"disabled", "revoked"} or binding.revoked_at is not None:
        return "revoked"
    if policy.policy_status in {"disabled", "revoked"}:
        return "revoked" if policy.policy_status == "revoked" else "outbound_disabled"
    if policy.channel_mute:
        return "muted"
    if policy.outbound_disabled:
        return "outbound_disabled"
    if not policy.low_frequency_checkin_enabled or setting is None or not setting.enabled:
        return "outbound_disabled"
    if payload.get("meaningful_silence"):
        return "meaningful_silence"
    if policy.focus_mode_enforced and _focus_active(s, policy.id):
        return "focus_mode"
    if policy.quiet_hours_enforced and _quiet_hours_active(s, policy.id):
        return "quiet_hours"
    if policy.remaining_presence_budget <= 0:
        return "presence_budget"
    if setting.next_eligible_at is not None and setting.next_eligible_at > _now():
        return "min_interval"
    return None


def _get_checkin_setting(s: Session, policy_id: uuid.UUID) -> ChannelCheckinSetting | None:
    return s.execute(
        select(ChannelCheckinSetting).where(ChannelCheckinSetting.channel_presence_policy_id == policy_id).limit(1)
    ).scalar_one_or_none()


def _focus_active(s: Session, policy_id: uuid.UUID) -> bool:
    return (
        s.execute(
            select(ChannelFocusModeRule)
            .where(ChannelFocusModeRule.channel_presence_policy_id == policy_id, ChannelFocusModeRule.focus_status == "active")
            .limit(1)
        ).scalar_one_or_none()
        is not None
    )


def _quiet_hours_active(s: Session, policy_id: uuid.UUID) -> bool:
    now = _now()
    minute = now.hour * 60 + now.minute
    rules = list(
        s.execute(
            select(ChannelQuietHourRule).where(
                ChannelQuietHourRule.channel_presence_policy_id == policy_id,
                ChannelQuietHourRule.enabled.is_(True),
                ChannelQuietHourRule.applies_to_checkins.is_(True),
            )
        ).scalars().all()
    )
    for rule in rules:
        if rule.start_minute_of_day <= rule.end_minute_of_day:
            if rule.start_minute_of_day <= minute <= rule.end_minute_of_day:
                return True
        elif minute >= rule.start_minute_of_day or minute <= rule.end_minute_of_day:
            return True
    return False


def _upsert_focus_rule(s: Session, policy_id: uuid.UUID, payload: dict[str, Any]) -> None:
    rule = s.execute(select(ChannelFocusModeRule).where(ChannelFocusModeRule.channel_presence_policy_id == policy_id).limit(1)).scalar_one_or_none()
    if rule is None:
        rule = ChannelFocusModeRule(channel_presence_policy_id=policy_id)
        s.add(rule)
    rule.focus_status = payload.get("focus_status") or "inactive"
    rule.suppresses_outbound = True
    rule.suppresses_checkins = True
    rule.focus_reason = payload.get("focus_reason")
    rule.updated_at = _now()


def _upsert_quiet_rule(s: Session, policy_id: uuid.UUID, payload: dict[str, Any]) -> None:
    rule = s.execute(select(ChannelQuietHourRule).where(ChannelQuietHourRule.channel_presence_policy_id == policy_id).limit(1)).scalar_one_or_none()
    if rule is None:
        rule = ChannelQuietHourRule(channel_presence_policy_id=policy_id, start_minute_of_day=0, end_minute_of_day=0)
        s.add(rule)
    rule.enabled = bool(payload.get("enabled", True))
    rule.timezone = payload.get("timezone") or "UTC"
    rule.start_minute_of_day = max(0, min(1439, int(payload.get("start_minute_of_day", 0))))
    rule.end_minute_of_day = max(0, min(1439, int(payload.get("end_minute_of_day", 1439))))
    rule.applies_to_checkins = True
    rule.applies_to_outbound = True
    rule.updated_at = _now()


def _record_budget_event(
    s: Session,
    policy: ChannelPresencePolicy,
    event_type: str,
    delta: int,
    summary: str,
) -> ChannelPresenceBudgetEvent:
    event = ChannelPresenceBudgetEvent(
        channel_presence_policy_id=policy.id,
        event_type=event_type,
        budget_delta=delta,
        remaining_budget=policy.remaining_presence_budget,
        event_summary=summary,
        event_json={"presence_mode": policy.presence_mode},
        occurred_at=_now(),
        metadata_={"implementation_origin": "channel_presence"},
    )
    s.add(event)
    return event


def _record_suppression(
    s: Session,
    policy: ChannelPresencePolicy,
    reason: str,
    summary: str,
) -> ChannelOutboundSuppressionEvent:
    persisted_reason = "outbound_disabled" if reason == "min_interval" else reason
    event = ChannelOutboundSuppressionEvent(
        channel_presence_policy_id=policy.id,
        suppression_reason=persisted_reason,
        suppression_status="applied",
        suppression_summary=summary,
        safe_suppression_json={"checkin": True, "algorithm_reason": reason},
        occurred_at=_now(),
        metadata_={"implementation_origin": "channel_presence"},
    )
    s.add(event)
    return event


def _record_meaningful_silence(s: Session, policy: ChannelPresencePolicy, payload: dict[str, Any]) -> ChannelMeaningfulSilenceEvent:
    event = ChannelMeaningfulSilenceEvent(
        channel_presence_policy_id=policy.id,
        silence_reason=_normalize_silence_reason(payload.get("silence_reason")),
        suppressed_outbound_count=1,
        silence_summary=payload.get("silence_summary") or "Check-in suppressed by meaningful silence",
        event_json=_safe_json(payload.get("event_json")),
        occurred_at=_now(),
        metadata_={"implementation_origin": "channel_presence"},
    )
    s.add(event)
    return event


def _policy_bundle(s: Session, policy: ChannelPresencePolicy) -> dict[str, Any]:
    setting = _get_checkin_setting(s, policy.id)
    return {
        **_policy_to_dict(policy),
        "checkin_setting": _checkin_to_dict(setting) if setting else None,
    }


def _policy_to_dict(row: ChannelPresencePolicy) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "companion_id": str(row.companion_id),
        "channel_binding_id": str(row.channel_binding_id),
        "provider_id": str(row.provider_id),
        "provider_bot_id": str(row.provider_bot_id) if row.provider_bot_id else None,
        "policy_status": row.policy_status,
        "presence_mode": row.presence_mode,
        "reply_only_default": row.reply_only_default,
        "low_frequency_checkin_enabled": row.low_frequency_checkin_enabled,
        "channel_mute": row.channel_mute,
        "outbound_disabled": row.outbound_disabled,
        "daily_presence_budget": row.daily_presence_budget,
        "remaining_presence_budget": row.remaining_presence_budget,
        "quiet_hours_enforced": row.quiet_hours_enforced,
        "focus_mode_enforced": row.focus_mode_enforced,
        "meaningful_silence_enforced": row.meaningful_silence_enforced,
        "policy_json": row.policy_json or {},
    }


def _checkin_to_dict(row: ChannelCheckinSetting) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "channel_presence_policy_id": str(row.channel_presence_policy_id),
        "enabled": row.enabled,
        "frequency": row.frequency,
        "min_interval_seconds": row.min_interval_seconds,
        "requires_user_opt_in": row.requires_user_opt_in,
        "quiet_hours_enforced": row.quiet_hours_enforced,
        "focus_mode_enforced": row.focus_mode_enforced,
        "presence_budget_enforced": row.presence_budget_enforced,
        "meaningful_silence_enforced": row.meaningful_silence_enforced,
        "next_eligible_at": row.next_eligible_at.isoformat() if row.next_eligible_at else None,
    }


def _suppression_to_dict(row: ChannelOutboundSuppressionEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "channel_presence_policy_id": str(row.channel_presence_policy_id),
        "suppression_reason": row.suppression_reason,
        "suppression_status": row.suppression_status,
        "suppression_summary": row.suppression_summary,
        "safe_suppression_json": row.safe_suppression_json or {},
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
    }


def _budget_event_to_dict(row: ChannelPresenceBudgetEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "channel_presence_policy_id": str(row.channel_presence_policy_id),
        "event_type": row.event_type,
        "budget_delta": row.budget_delta,
        "remaining_budget": row.remaining_budget,
        "event_summary": row.event_summary,
        "event_json": row.event_json or {},
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
    }


def _safe_json(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return _scrub(value)


def _normalize_silence_reason(value: Any) -> str:
    if not value:
        return "manual"
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    normalized = _SILENCE_REASON_ALIASES.get(normalized, normalized)
    return normalized if normalized in _SILENCE_REASON_VALUES else "manual"


def _scrub(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if any(part in key_text.lower().replace("-", "_") for part in _SENSITIVE_KEY_PARTS):
                continue
            result[key_text] = _scrub(item)
        return result
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def _to_uuid(value: Any) -> uuid.UUID | None:
    if not value:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _now() -> datetime:
    return datetime.now(timezone.utc)
