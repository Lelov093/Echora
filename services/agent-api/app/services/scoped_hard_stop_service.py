"""Realtime compatibility scoped hard stop service."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from app.db.models import (
    CompanionResidentStatusEvent,
    HardStopAuditEvent,
    MultimodalContextEvent,
    RealtimeCoPresenceParticipant,
    RealtimeCoPresenceSession,
    RealtimeSessionChannel,
    RealtimeSessionStateEvent,
    ScopedHardStopEvent,
    User,
)
from app.services.realtime_copresence_service import get_session


def trigger_scoped_hard_stop(user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    scope = payload.get("hard_stop_scope")
    if scope == "session":
        return stop_session_scope(user_id, payload)
    if scope == "channel":
        return stop_channel_scope(user_id, payload)
    if scope == "companion":
        return stop_companion_scope(user_id, payload)
    if scope == "sensor":
        return stop_sensor_scope(user_id, payload)
    return _create_hard_stop(user_id, {**payload, "hard_stop_scope": "all_realtime"})


def stop_session_scope(user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    return _create_hard_stop(user_id, {**payload, "hard_stop_scope": "session"})


def stop_channel_scope(user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    return _create_hard_stop(user_id, {**payload, "hard_stop_scope": "channel"})


def stop_companion_scope(user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    return _create_hard_stop(user_id, {**payload, "hard_stop_scope": "companion"})


def stop_sensor_scope(user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    return _create_hard_stop(user_id, {**payload, "hard_stop_scope": "sensor"})


def write_hard_stop_audit(s, event: ScopedHardStopEvent, audit_type: str = "enforced") -> HardStopAuditEvent:
    audit = HardStopAuditEvent(
        user_id=event.user_id,
        hard_stop_event_id=event.id,
        audit_event_type=audit_type if audit_type in {"created", "enforced", "released", "violation_detected", "expired"} else "enforced",
        audit_status="recorded",
        affected_scope=event.hard_stop_scope,
        audit_summary=event.stop_reason or f"Hard stop enforced for {event.hard_stop_scope}",
        audit_payload_json={
            "stops_listening": event.stops_listening,
            "stops_speaking": event.stops_speaking,
            "stops_observing": event.stops_observing,
            "stops_memory_capture": event.stops_memory_capture,
            "stops_context_capture": event.stops_context_capture,
        },
        occurred_at=_now(),
        metadata_={"implementation_origin": "resident_presence"},
    )
    s.add(audit)
    return audit


def _create_hard_stop(user_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any] | None:
    with get_session() as s:
        user = s.get(User, user_id)
        if user is None:
            return None
        scope = payload.get("hard_stop_scope")
        target = _target_for_scope(payload)
        if scope not in {"session", "channel", "companion", "sensor", "all_realtime"} or target is None:
            return None
        event = ScopedHardStopEvent(
            user_id=user_id,
            hard_stop_scope=scope,
            hard_stop_status="active",
            initiated_by=payload.get("initiated_by") if payload.get("initiated_by") in {"user", "boundary_policy", "system"} else "user",
            realtime_session_id=_to_uuid(payload.get("realtime_session_id")),
            channel_id=_to_uuid(payload.get("channel_id")),
            companion_id=_to_uuid(payload.get("companion_id")),
            context_event_id=_to_uuid(payload.get("context_event_id")),
            stop_reason=payload.get("stop_reason") or "User requested hard stop",
            stops_listening=True,
            stops_speaking=True,
            stops_observing=True,
            stops_memory_capture=True,
            stops_context_capture=True,
            requires_audit=True,
            policy_snapshot_json={"hard_stop_scope": scope, "audit_required": True},
            metadata_={"implementation_origin": "resident_presence"},
        )
        s.add(event)
        s.flush()
        _enforce_scope(s, event)
        audit = write_hard_stop_audit(s, event, "enforced")
        s.commit()
        s.refresh(event)
        s.refresh(audit)
        return {"hard_stop": _hard_stop_to_dict(event), "audit": _audit_to_dict(audit)}


def _target_for_scope(payload: dict[str, Any]) -> str | None:
    scope = payload.get("hard_stop_scope")
    if scope == "session":
        return payload.get("realtime_session_id")
    if scope == "channel":
        return payload.get("channel_id")
    if scope == "companion":
        return payload.get("companion_id")
    if scope == "sensor":
        return payload.get("context_event_id")
    if scope == "all_realtime":
        return "all"
    return None


def _enforce_scope(s, event: ScopedHardStopEvent) -> None:
    now = _now()
    if event.hard_stop_scope == "session" and event.realtime_session_id:
        session = s.get(RealtimeCoPresenceSession, event.realtime_session_id)
        if session:
            previous = session.session_status
            session.session_status = "ended"
            session.ended_at = now
            session.last_event_at = now
            s.add(
                RealtimeSessionStateEvent(
                    user_id=event.user_id,
                    realtime_session_id=session.id,
                    event_type="hard_stop.triggered",
                    event_status="recorded",
                    previous_status=previous,
                    next_status="ended",
                    event_payload_json={"hard_stop_event_id": str(event.id), "scope": event.hard_stop_scope},
                    permission_snapshot_json=session.permission_snapshot_json or {},
                    occurred_at=now,
                    metadata_={"implementation_origin": "resident_presence"},
                )
            )
            for channel in s.execute(
                select(RealtimeSessionChannel).where(RealtimeSessionChannel.realtime_session_id == session.id)
            ).scalars():
                channel.channel_status = "closed"
                channel.closed_at = now
                channel.last_event_at = now
            for participant in s.execute(
                select(RealtimeCoPresenceParticipant).where(RealtimeCoPresenceParticipant.realtime_session_id == session.id)
            ).scalars():
                participant.participant_status = "left"
                participant.left_at = participant.left_at or now
                participant.can_listen = False
                participant.can_speak = False
                participant.can_remember = False
                participant.can_receive_transcript = False
    elif event.hard_stop_scope == "channel" and event.channel_id:
        channel = s.get(RealtimeSessionChannel, event.channel_id)
        if channel:
            channel.channel_status = "closed"
            channel.can_send_events = False
            channel.can_receive_actions = False
            channel.closed_at = now
            channel.last_event_at = now
    elif event.hard_stop_scope == "companion" and event.companion_id:
        s.add(
            CompanionResidentStatusEvent(
                user_id=event.user_id,
                companion_id=event.companion_id,
                realtime_session_id=event.realtime_session_id,
                status_type="hard_stopped",
                status_source="boundary_policy",
                interruption_level="none",
                allows_unsolicited_presence=False,
                presence_summary=event.stop_reason,
                policy_snapshot_json={"hard_stop_event_id": str(event.id)},
                occurred_at=now,
                metadata_={"implementation_origin": "resident_presence"},
            )
        )
        for participant in s.execute(
            select(RealtimeCoPresenceParticipant).where(
                RealtimeCoPresenceParticipant.participant_companion_id == event.companion_id
            )
        ).scalars():
            participant.participant_status = "removed"
            participant.can_listen = False
            participant.can_speak = False
            participant.can_remember = False
            participant.can_receive_transcript = False
    elif event.hard_stop_scope == "sensor" and event.context_event_id:
        context = s.get(MultimodalContextEvent, event.context_event_id)
        if context:
            context.context_status = "blocked"
            context.raw_data_ref = None
            context.raw_data_storage_allowed = False


def _hard_stop_to_dict(event: ScopedHardStopEvent) -> dict[str, Any]:
    return {
        "id": str(event.id),
        "user_id": str(event.user_id),
        "hard_stop_scope": event.hard_stop_scope,
        "hard_stop_status": event.hard_stop_status,
        "initiated_by": event.initiated_by,
        "realtime_session_id": str(event.realtime_session_id) if event.realtime_session_id else None,
        "channel_id": str(event.channel_id) if event.channel_id else None,
        "companion_id": str(event.companion_id) if event.companion_id else None,
        "context_event_id": str(event.context_event_id) if event.context_event_id else None,
        "stop_reason": event.stop_reason,
        "stops_listening": event.stops_listening,
        "stops_speaking": event.stops_speaking,
        "stops_observing": event.stops_observing,
        "stops_memory_capture": event.stops_memory_capture,
        "stops_context_capture": event.stops_context_capture,
        "requires_audit": event.requires_audit,
        "policy_snapshot_json": event.policy_snapshot_json or {},
    }


def _audit_to_dict(audit: HardStopAuditEvent) -> dict[str, Any]:
    return {
        "id": str(audit.id),
        "hard_stop_event_id": str(audit.hard_stop_event_id),
        "audit_event_type": audit.audit_event_type,
        "audit_status": audit.audit_status,
        "affected_scope": audit.affected_scope,
        "audit_summary": audit.audit_summary,
        "audit_payload_json": audit.audit_payload_json or {},
    }


def _to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _now() -> datetime:
    return datetime.now(timezone.utc)
