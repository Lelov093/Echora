"""Channel Gateway provider-neutral channel message and delivery service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    ChannelAuditLog,
    ChannelBinding,
    ChannelDeliveryEvent,
    ChannelMessageEvent,
    ChannelOutboundAuditEvent,
    ChannelTraceEvent,
    CompanionIdentityProfile,
)

_engine = None
_SENSITIVE_KEY_PARTS = ("token", "secret", "password", "api_key", "authorization", "credential", "raw")


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def list_message_events(
    *,
    channel_binding_id: uuid.UUID | None = None,
    direction: str | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(ChannelMessageEvent)
        if channel_binding_id is not None:
            stmt = stmt.where(ChannelMessageEvent.channel_binding_id == channel_binding_id)
        if direction:
            stmt = stmt.where(ChannelMessageEvent.message_direction == direction)
        if status:
            stmt = stmt.where(ChannelMessageEvent.message_status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = list(
            s.execute(
                stmt.order_by(ChannelMessageEvent.occurred_at.desc(), ChannelMessageEvent.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
        )
        return {"items": [_message_to_dict(item) for item in items], "total": total}


def list_delivery_events(
    *,
    channel_binding_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    with get_session() as s:
        stmt = select(ChannelDeliveryEvent)
        if channel_binding_id is not None:
            stmt = stmt.where(ChannelDeliveryEvent.channel_binding_id == channel_binding_id)
        if status:
            stmt = stmt.where(ChannelDeliveryEvent.delivery_status == status)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        items = list(
            s.execute(
                stmt.order_by(ChannelDeliveryEvent.queued_at.desc(), ChannelDeliveryEvent.created_at.desc())
                .offset((page - 1) * page_size)
                .limit(page_size)
            ).scalars().all()
        )
        return {"items": [_delivery_to_dict(item) for item in items], "total": total}


def ingest_inbound(payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        binding = s.get(ChannelBinding, _to_uuid(payload.get("channel_binding_id")))
        if binding is None or binding.presence_channel_binding_id is None:
            return None
        if binding.binding_status == "revoked" or not binding.can_receive_inbound:
            return None

        message = ChannelMessageEvent(
            user_id=binding.user_id,
            presence_channel_binding_id=binding.presence_channel_binding_id,
            companion_id=binding.companion_id,
            channel_permission_policy_id=None,
            message_direction="inbound",
            message_status="recorded",
            message_summary=_summary(payload),
            raw_message_ref=None,
            raw_message_storage_allowed=False,
            memory_candidate_policy="review_required",
            requires_user_review=True,
            redaction_status="pending",
            message_payload_json={"safe_summary": _summary(payload)},
            occurred_at=_now(),
            channel_binding_id=binding.id,
            provider_id=binding.provider_id,
            provider_bot_id=binding.provider_bot_id,
            trace_run_id=_to_uuid(payload.get("trace_run_id")),
            external_message_ref_hash=payload.get("external_message_ref_hash"),
            external_conversation_ref_hash=payload.get("external_conversation_ref_hash"),
            idempotency_key=payload.get("idempotency_key"),
            payload_is_ephemeral=True,
            raw_payload_storage_allowed=False,
            safe_payload_json=_safe_json(payload.get("safe_payload_json")),
            metadata_={"implementation_origin": "channel_message", "provider_neutral": True},
        )
        s.add(message)
        s.flush()
        trace = _record_trace(s, binding, "inbound", "recorded", "Inbound channel message recorded", message.id)
        _record_audit(s, binding, "message_received", "Inbound channel message recorded", trace.id)
        s.commit()
        s.refresh(message)
        return {
            "message": _message_to_dict(message),
            "trace_event_id": str(trace.id),
            "memory_write": "not_written_review_required",
        }


def queue_outbound(payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        binding = s.get(ChannelBinding, _to_uuid(payload.get("channel_binding_id")))
        if binding is None or binding.presence_channel_binding_id is None:
            return None
        reply_to = _load_reply_context(s, binding, payload)
        profile_status = s.execute(
            select(CompanionIdentityProfile.profile_status).where(
                CompanionIdentityProfile.companion_id == binding.companion_id
            )
        ).scalar_one_or_none() if binding.companion_id else None
        allowed, reason = _outbound_allowed(binding, reply_to, profile_status == "archived")
        status = "queued" if allowed else "suppressed"

        message = ChannelMessageEvent(
            user_id=binding.user_id,
            presence_channel_binding_id=binding.presence_channel_binding_id,
            companion_id=binding.companion_id,
            message_direction="outbound",
            message_status="queued" if allowed else "suppressed",
            message_summary=_summary(payload),
            raw_message_ref=None,
            raw_message_storage_allowed=False,
            memory_candidate_policy="review_required",
            requires_user_review=True,
            redaction_status="pending",
            message_payload_json={"safe_summary": _summary(payload), "reply_to_message_event_id": str(reply_to.id) if reply_to else None},
            occurred_at=_now(),
            channel_binding_id=binding.id,
            provider_id=binding.provider_id,
            provider_bot_id=binding.provider_bot_id,
            trace_run_id=_to_uuid(payload.get("trace_run_id")),
            external_conversation_ref_hash=payload.get("external_conversation_ref_hash"),
            idempotency_key=payload.get("idempotency_key"),
            payload_is_ephemeral=True,
            raw_payload_storage_allowed=False,
            safe_payload_json=_safe_json(payload.get("safe_payload_json")),
            metadata_={"implementation_origin": "channel_message", "provider_neutral": True},
        )
        s.add(message)
        s.flush()

        delivery = ChannelDeliveryEvent(
            user_id=binding.user_id,
            channel_binding_id=binding.id,
            channel_message_event_id=message.id,
            provider_id=binding.provider_id,
            provider_bot_id=binding.provider_bot_id,
            trace_run_id=_to_uuid(payload.get("trace_run_id")),
            delivery_status=status,
            delivery_mode="reply_only",
            delivery_attempt=1,
            external_delivery_ref_hash=payload.get("external_delivery_ref_hash"),
            delivery_summary="Provider-neutral outbound queued" if allowed else f"Outbound suppressed: {reason}",
            raw_payload_storage_allowed=False,
            safe_delivery_payload_json={
                "policy": binding.outbound_policy,
                "reason": reason,
                "reply_to_message_event_id": str(reply_to.id) if reply_to else None,
                **_safe_json(payload.get("safe_delivery_payload_json")),
            },
            queued_at=_now(),
            delivered_at=None,
            metadata_={"implementation_origin": "channel_message", "real_provider_send": False},
        )
        s.add(delivery)
        s.flush()
        trace_status = "recorded" if allowed else "suppressed"
        trace = _record_trace(s, binding, "outbound", trace_status, delivery.delivery_summary, message.id, delivery.id)
        audit = ChannelOutboundAuditEvent(
            user_id=binding.user_id,
            channel_binding_id=binding.id,
            channel_delivery_event_id=delivery.id,
            channel_message_event_id=message.id,
            provider_bot_id=binding.provider_bot_id,
            outbound_audit_status=status,
            outbound_policy_snapshot=binding.outbound_policy,
            audit_summary=delivery.delivery_summary,
            safe_outbound_audit_json=delivery.safe_delivery_payload_json,
            occurred_at=_now(),
            metadata_={"implementation_origin": "channel_message"},
        )
        s.add(audit)
        _record_audit(s, binding, "message_sent", delivery.delivery_summary, trace.id)
        s.commit()
        s.refresh(message)
        s.refresh(delivery)
        s.refresh(audit)
        return {
            "message": _message_to_dict(message),
            "delivery": _delivery_to_dict(delivery),
            "outbound_audit": _outbound_audit_to_dict(audit),
            "policy_decision": "allowed" if allowed else "suppressed",
            "policy_reason": reason,
            "real_provider_send": False,
        }


def _load_reply_context(s: Session, binding: ChannelBinding, payload: dict[str, Any]) -> ChannelMessageEvent | None:
    reply_to_id = _to_uuid(payload.get("reply_to_message_event_id"))
    if reply_to_id is None:
        return None
    message = s.get(ChannelMessageEvent, reply_to_id)
    if (
        message is None
        or message.channel_binding_id != binding.id
        or message.message_direction != "inbound"
        or message.message_status != "recorded"
    ):
        return None
    return message


def _outbound_allowed(binding: ChannelBinding, reply_to: ChannelMessageEvent | None, companion_archived: bool = False) -> tuple[bool, str]:
    if companion_archived:
        return False, "companion_archived"
    if binding.binding_status not in {"draft", "active"}:
        return False, "binding_not_active"
    if binding.outbound_policy == "disabled" or not binding.can_send_outbound:
        return False, "outbound_disabled"
    if binding.outbound_policy == "reply_only" and reply_to is None:
        return False, "reply_only_requires_inbound_context"
    if binding.provider_bot_id is None:
        return False, "provider_bot_required"
    return True, "reply_only_context_allowed"


def _record_trace(
    s: Session,
    binding: ChannelBinding,
    trace_event_type: str,
    trace_status: str,
    summary: str,
    message_id: uuid.UUID | None = None,
    delivery_id: uuid.UUID | None = None,
) -> ChannelTraceEvent:
    event = ChannelTraceEvent(
        user_id=binding.user_id,
        companion_id=binding.companion_id,
        channel_binding_id=binding.id,
        provider_id=binding.provider_id,
        provider_bot_id=binding.provider_bot_id,
        channel_message_event_id=message_id,
        channel_delivery_event_id=delivery_id,
        trace_event_type=trace_event_type,
        trace_status=trace_status,
        trace_summary=summary,
        safe_trace_payload_json={"raw_payload_storage_allowed": False},
        occurred_at=_now(),
        metadata_={"implementation_origin": "channel_message"},
    )
    s.add(event)
    s.flush()
    return event


def _record_audit(
    s: Session,
    binding: ChannelBinding,
    audit_log_type: str,
    summary: str,
    trace_event_id: uuid.UUID | None = None,
) -> ChannelAuditLog:
    audit = ChannelAuditLog(
        user_id=binding.user_id,
        channel_binding_id=binding.id,
        provider_id=binding.provider_id,
        provider_bot_id=binding.provider_bot_id,
        channel_trace_event_id=trace_event_id,
        audit_log_type=audit_log_type,
        audit_summary=summary,
        safe_audit_payload_json={"raw_payload_storage_allowed": False},
        occurred_at=_now(),
        metadata_={"implementation_origin": "channel_message"},
    )
    s.add(audit)
    return audit


def _message_to_dict(row: ChannelMessageEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "presence_channel_binding_id": str(row.presence_channel_binding_id),
        "channel_binding_id": str(row.channel_binding_id) if row.channel_binding_id else None,
        "provider_id": str(row.provider_id) if row.provider_id else None,
        "provider_bot_id": str(row.provider_bot_id) if row.provider_bot_id else None,
        "companion_id": str(row.companion_id) if row.companion_id else None,
        "message_direction": row.message_direction,
        "message_status": row.message_status,
        "message_summary": row.message_summary,
        "memory_candidate_policy": row.memory_candidate_policy,
        "requires_user_review": row.requires_user_review,
        "payload_is_ephemeral": row.payload_is_ephemeral,
        "raw_payload_storage_allowed": row.raw_payload_storage_allowed,
        "safe_payload_json": row.safe_payload_json or {},
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
    }


def _delivery_to_dict(row: ChannelDeliveryEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "channel_binding_id": str(row.channel_binding_id),
        "channel_message_event_id": str(row.channel_message_event_id) if row.channel_message_event_id else None,
        "provider_id": str(row.provider_id),
        "provider_bot_id": str(row.provider_bot_id) if row.provider_bot_id else None,
        "delivery_status": row.delivery_status,
        "delivery_mode": row.delivery_mode,
        "delivery_attempt": row.delivery_attempt,
        "delivery_summary": row.delivery_summary,
        "raw_payload_storage_allowed": row.raw_payload_storage_allowed,
        "safe_delivery_payload_json": row.safe_delivery_payload_json or {},
        "queued_at": row.queued_at.isoformat() if row.queued_at else None,
        "delivered_at": row.delivered_at.isoformat() if row.delivered_at else None,
    }


def _outbound_audit_to_dict(row: ChannelOutboundAuditEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "channel_binding_id": str(row.channel_binding_id),
        "channel_delivery_event_id": str(row.channel_delivery_event_id) if row.channel_delivery_event_id else None,
        "channel_message_event_id": str(row.channel_message_event_id) if row.channel_message_event_id else None,
        "provider_bot_id": str(row.provider_bot_id) if row.provider_bot_id else None,
        "outbound_audit_status": row.outbound_audit_status,
        "outbound_policy_snapshot": row.outbound_policy_snapshot,
        "audit_summary": row.audit_summary,
        "safe_outbound_audit_json": row.safe_outbound_audit_json or {},
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
    }


def _summary(payload: dict[str, Any]) -> str:
    return _truncate(str(payload.get("message_summary") or payload.get("safe_summary") or "Channel message event"), 500)


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
    return value


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
