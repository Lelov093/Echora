"""Channel Gateway cross-channel continuity and handoff service."""

import re
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import ChannelAuditLog, ChannelBinding, ChannelTraceEvent

_engine = None
_SENSITIVE_KEY_PARTS = (
    "token",
    "secret",
    "password",
    "api_key",
    "authorization",
    "credential",
    "raw",
    "private",
    "memory_content",
    "full_history",
    "transcript",
)
_TOKEN_PATTERN = re.compile(r"(sk-[A-Za-z0-9_\-]{8,}|[A-Za-z0-9_\-]{24,}\.[A-Za-z0-9_\-]{6,}\.[A-Za-z0-9_\-]{20,})")


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def list_handoffs(
    *,
    channel_binding_id: uuid.UUID | None = None,
    companion_id: uuid.UUID | None = None,
    direction: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(ChannelTraceEvent).where(ChannelTraceEvent.trace_event_type == "adapter")
        if channel_binding_id is not None:
            stmt = stmt.where(ChannelTraceEvent.channel_binding_id == channel_binding_id)
        if companion_id is not None:
            stmt = stmt.where(ChannelTraceEvent.companion_id == companion_id)
        if status:
            stmt = stmt.where(ChannelTraceEvent.trace_status == status)
        items = list(
            s.execute(
                stmt.order_by(ChannelTraceEvent.occurred_at.desc())
            ).scalars().all()
        )
        filtered = [
            item
            for item in items
            if (item.safe_trace_payload_json or {}).get("event_family") == "channel_continuity_handoff"
            and (direction is None or (item.safe_trace_payload_json or {}).get("direction") == direction)
        ]
        total = len(filtered)
        start = (page - 1) * page_size
        return {"items": [_handoff_to_dict(item) for item in filtered[start : start + page_size]], "total": total}


def create_web_to_channel_handoff(payload: dict[str, Any]) -> dict[str, Any] | None:
    return _create_handoff("web_to_channel", payload)


def create_channel_to_web_handoff(payload: dict[str, Any]) -> dict[str, Any] | None:
    return _create_handoff("channel_to_web", payload)


def _create_handoff(direction: str, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        binding = s.get(ChannelBinding, _to_uuid(payload.get("channel_binding_id")))
        if binding is None:
            return None

        allowed, reason = _handoff_allowed(binding, payload)
        trace_status = "recorded" if allowed else "suppressed"
        summary = _continuity_summary(direction, payload, allowed, reason)
        safe_payload = {
            "event_family": "channel_continuity_handoff",
            "direction": direction,
            "handoff_status": "authorized" if allowed else "blocked",
            "visibility_policy_ack": bool(payload.get("visibility_policy_ack")),
            "boundary_policy_ack": bool(payload.get("boundary_policy_ack")),
            "continuity_summary": summary,
            "handoff_reason": _redact_text(str(payload.get("handoff_reason") or ""))[:300],
            "visibility_decision": "allowed" if allowed else "blocked",
            "visibility_reason": reason,
            "raw_history_included": False,
            "private_memory_included": False,
            "safe_context_json": _safe_json(payload.get("safe_context_json")) if allowed else {},
        }
        trace = ChannelTraceEvent(
            user_id=binding.user_id,
            companion_id=binding.companion_id,
            channel_binding_id=binding.id,
            provider_id=binding.provider_id,
            provider_bot_id=binding.provider_bot_id,
            trace_run_id=_to_uuid(payload.get("trace_run_id")),
            trace_event_type="adapter",
            trace_status=trace_status,
            trace_summary=summary,
            safe_trace_payload_json=safe_payload,
            occurred_at=_now(),
            metadata_={"implementation_origin": "channel_continuity", "continuity_summary_only": True},
        )
        s.add(trace)
        s.flush()
        audit = ChannelAuditLog(
            user_id=binding.user_id,
            channel_binding_id=binding.id,
            provider_id=binding.provider_id,
            provider_bot_id=binding.provider_bot_id,
            channel_trace_event_id=trace.id,
            audit_log_type="binding_updated",
            audit_summary=summary,
            safe_audit_payload_json={
                "event_family": "channel_continuity_handoff",
                "direction": direction,
                "handoff_status": safe_payload["handoff_status"],
                "visibility_decision": safe_payload["visibility_decision"],
                "visibility_reason": reason,
                "raw_history_included": False,
                "private_memory_included": False,
            },
            occurred_at=_now(),
            metadata_={"implementation_origin": "channel_continuity"},
        )
        s.add(audit)
        s.commit()
        s.refresh(trace)
        s.refresh(audit)
        return {
            "handoff": _handoff_to_dict(trace),
            "audit": _audit_to_dict(audit),
            "continuity_summary": summary if allowed else "",
            "visibility_decision": safe_payload["visibility_decision"],
            "visibility_reason": reason,
            "raw_history_included": False,
            "private_memory_included": False,
        }


def _handoff_allowed(binding: ChannelBinding, payload: dict[str, Any]) -> tuple[bool, str]:
    if binding.binding_status != "active":
        return False, "binding_not_active"
    if binding.revoked_at is not None:
        return False, "binding_revoked"
    if not payload.get("visibility_policy_ack"):
        return False, "visibility_policy_ack_required"
    if not payload.get("boundary_policy_ack"):
        return False, "boundary_policy_ack_required"
    if payload.get("include_raw_history") or payload.get("include_private_memory"):
        return False, "raw_or_private_context_not_allowed"
    return True, "authorized_summary_only"


def _continuity_summary(direction: str, payload: dict[str, Any], allowed: bool, reason: str) -> str:
    requested = str(payload.get("continuity_summary") or payload.get("source_context_summary") or "")
    if not requested:
        requested = "Cross-channel continuity handoff requested"
    requested = _redact_text(requested)
    if not allowed:
        return f"{direction} handoff blocked: {reason}"
    return _truncate(f"{direction} continuity: {requested}", 500)


def _handoff_to_dict(row: ChannelTraceEvent) -> dict[str, Any]:
    payload = row.safe_trace_payload_json or {}
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "companion_id": str(row.companion_id) if row.companion_id else None,
        "channel_binding_id": str(row.channel_binding_id) if row.channel_binding_id else None,
        "provider_id": str(row.provider_id) if row.provider_id else None,
        "provider_bot_id": str(row.provider_bot_id) if row.provider_bot_id else None,
        "trace_event_type": row.trace_event_type,
        "trace_status": row.trace_status,
        "handoff_status": payload.get("handoff_status"),
        "direction": payload.get("direction"),
        "trace_summary": row.trace_summary,
        "visibility_decision": payload.get("visibility_decision"),
        "visibility_reason": payload.get("visibility_reason"),
        "raw_history_included": bool(payload.get("raw_history_included", False)),
        "private_memory_included": bool(payload.get("private_memory_included", False)),
        "safe_trace_payload_json": payload,
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
    }


def _audit_to_dict(row: ChannelAuditLog) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "channel_binding_id": str(row.channel_binding_id) if row.channel_binding_id else None,
        "provider_id": str(row.provider_id) if row.provider_id else None,
        "provider_bot_id": str(row.provider_bot_id) if row.provider_bot_id else None,
        "channel_trace_event_id": str(row.channel_trace_event_id) if row.channel_trace_event_id else None,
        "audit_log_type": row.audit_log_type,
        "audit_summary": row.audit_summary,
        "safe_audit_payload_json": row.safe_audit_payload_json or {},
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
    }


def _safe_json(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return _scrub(value)


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
    if isinstance(value, str):
        return _redact_text(value)
    return value


def _redact_text(value: str) -> str:
    return _TOKEN_PATTERN.sub("[redacted]", value)


def _to_uuid(value: Any) -> uuid.UUID | None:
    if not value:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(str(value))


def _truncate(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[: limit - 1].rstrip() + "."


def _now() -> datetime:
    return datetime.now(timezone.utc)
