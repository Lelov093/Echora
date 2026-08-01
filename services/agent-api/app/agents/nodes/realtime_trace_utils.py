"""Utilities for Realtime compatibility realtime graph trace nodes."""

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.state import RealtimeAgentState
from app.db.models import (
    MemoryGateTrace,
    PermissionAuditEvent,
    RealtimeTraceEvent,
    RealtimeTraceSession,
)


def now() -> datetime:
    return datetime.now(timezone.utc)


def to_uuid(value: Any) -> uuid.UUID | None:
    if value in (None, ""):
        return None
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def record_trace_event(
    s: Session,
    state: RealtimeAgentState,
    *,
    event_type: str,
    event_summary: str,
    source_participant_id: str | uuid.UUID | None = None,
    source_channel_id: str | uuid.UUID | None = None,
    event_payload_json: dict[str, Any] | None = None,
    event_status: str = "recorded",
) -> RealtimeTraceEvent:
    event = RealtimeTraceEvent(
        user_id=uuid.UUID(state["user_id"]),
        realtime_trace_session_id=uuid.UUID(state["realtime_trace_session_id"]),
        realtime_session_id=uuid.UUID(state["realtime_session_id"]),
        event_type=event_type,
        event_status=event_status,
        source_participant_id=to_uuid(source_participant_id),
        source_channel_id=to_uuid(source_channel_id),
        event_summary=event_summary,
        raw_payload_storage_allowed=False,
        raw_payload_retention_policy="ephemeral",
        event_payload_json=_safe_trace_payload(event_payload_json or {}),
        occurred_at=now(),
        metadata_={"implementation_origin": "realtime_trace"},
    )
    s.add(event)
    s.flush()
    state.setdefault("realtime_trace_event_ids", []).append(str(event.id))
    return event


def record_permission_audit(
    s: Session,
    state: RealtimeAgentState,
    *,
    audit_scope: str,
    audit_summary: str,
    realtime_trace_event_id: uuid.UUID | None = None,
    participant_id: str | uuid.UUID | None = None,
    context_event_id: str | uuid.UUID | None = None,
    hard_stop_event_id: str | uuid.UUID | None = None,
    audit_decision: str = "review_required",
    audit_payload_json: dict[str, Any] | None = None,
) -> PermissionAuditEvent:
    audit = PermissionAuditEvent(
        user_id=uuid.UUID(state["user_id"]),
        realtime_trace_session_id=uuid.UUID(state["realtime_trace_session_id"]),
        realtime_trace_event_id=realtime_trace_event_id,
        participant_id=to_uuid(participant_id),
        context_event_id=to_uuid(context_event_id),
        hard_stop_event_id=to_uuid(hard_stop_event_id),
        audit_scope=audit_scope,
        audit_decision=audit_decision,
        requires_redaction_review=True,
        audit_summary=audit_summary,
        audit_payload_json=audit_payload_json or {},
        occurred_at=now(),
        metadata_={"implementation_origin": "realtime_trace"},
    )
    s.add(audit)
    s.flush()
    state.setdefault("permission_audit_event_ids", []).append(str(audit.id))
    return audit


def record_memory_gate(
    s: Session,
    state: RealtimeAgentState,
    *,
    realtime_trace_event_id: uuid.UUID | None,
    memory_buffer_id: str | uuid.UUID | None = None,
    gate_status: str = "review_required",
    gate_summary: str = "Realtime memory write remains review-gated.",
    gate_payload_json: dict[str, Any] | None = None,
) -> MemoryGateTrace:
    gate = MemoryGateTrace(
        user_id=uuid.UUID(state["user_id"]),
        realtime_trace_session_id=uuid.UUID(state["realtime_trace_session_id"]),
        realtime_trace_event_id=realtime_trace_event_id,
        memory_buffer_id=to_uuid(memory_buffer_id),
        gate_status=gate_status,
        auto_write_blocked=True,
        gate_summary=gate_summary,
        gate_payload_json=gate_payload_json or {},
        metadata_={"implementation_origin": "realtime_trace"},
    )
    s.add(gate)
    s.flush()
    state.setdefault("memory_gate_trace_ids", []).append(str(gate.id))
    return gate


def load_trace_session(s: Session, state: RealtimeAgentState) -> RealtimeTraceSession | None:
    trace_id = state.get("realtime_trace_session_id")
    if trace_id:
        return s.get(RealtimeTraceSession, uuid.UUID(trace_id))
    return (
        s.execute(
            select(RealtimeTraceSession)
            .where(RealtimeTraceSession.realtime_session_id == uuid.UUID(state["realtime_session_id"]))
            .order_by(RealtimeTraceSession.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
    )


def append_step(state: RealtimeAgentState, *, step: str, order: int, status: str = "completed", **payload: Any) -> None:
    state.setdefault("trace_steps", []).append({"step": step, "order": order, "status": status, **payload})


def _safe_trace_payload(value: Any) -> Any:
    """Strip secret/raw payload fields while preserving explicit disabled flags."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        redacted: list[str] = []
        for key, item in value.items():
            normalized = str(key).lower()
            sensitive_key = any(marker in normalized for marker in ("token", "secret", "api_key", "password"))
            raw_key = any(marker in normalized for marker in ("raw_payload", "raw_content", "raw_audio", "raw_video", "raw_screen"))
            if sensitive_key or (raw_key and item not in (False, None, "", 0)):
                redacted.append(str(key))
                continue
            result[str(key)] = _safe_trace_payload(item)
        if redacted:
            result["redacted_fields"] = sorted(redacted)
        return result
    if isinstance(value, list):
        return [_safe_trace_payload(item) for item in value[:100]]
    if isinstance(value, str):
        return value[:1000]
    return value


def public_row(row: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    data: dict[str, Any] = {"id": str(row.id)}
    for field in fields:
        value = getattr(row, field)
        if isinstance(value, uuid.UUID):
            data[field] = str(value)
        elif isinstance(value, datetime):
            data[field] = value.isoformat()
        else:
            data[field] = value
    return data
