"""Enforce and trace a compatibility-only scoped hard stop."""

import uuid

from sqlalchemy import select

from app.agents.state import RealtimeAgentState
from app.agents.nodes.realtime_trace_utils import append_step, record_permission_audit, record_trace_event
from app.db.models import RealtimeSessionChannel, ScopedHardStopEvent
from app.services import scoped_hard_stop_service
from app.services.trace_service import get_session


def scoped_hard_stop_node(state: RealtimeAgentState) -> RealtimeAgentState:
    scope = state.get("hard_stop_scope") or "channel"
    with get_session() as s:
        existing = (
            s.execute(
                select(ScopedHardStopEvent)
                .where(
                    ScopedHardStopEvent.user_id == uuid.UUID(state["user_id"]),
                    ScopedHardStopEvent.realtime_session_id == uuid.UUID(state["realtime_session_id"]),
                )
                .order_by(ScopedHardStopEvent.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
        )

    if existing is None:
        payload = {"stop_reason": "Realtime graph hard stop trace checkpoint"}
        if scope == "session":
            payload["realtime_session_id"] = state["realtime_session_id"]
        elif scope == "companion":
            payload["companion_id"] = state["companion_id"]
        elif scope == "sensor":
            payload["context_event_id"] = state.get("hard_stop_target_id")
        else:
            payload["channel_id"] = state.get("hard_stop_target_id") or state.get("default_channel_id") or _default_channel_id(state)
            scope = "channel"
        stop = scoped_hard_stop_service.trigger_scoped_hard_stop(uuid.UUID(state["user_id"]), {"hard_stop_scope": scope, **payload}) or {}
        hard_stop = stop.get("hard_stop") or {}
    else:
        hard_stop = {
            "id": str(existing.id),
            "hard_stop_scope": existing.hard_stop_scope,
            "hard_stop_status": existing.hard_stop_status,
            "requires_audit": existing.requires_audit,
        }

    with get_session() as s:
        event = record_trace_event(
            s,
            state,
            event_type="hard_stop",
            event_summary=f"Scoped hard stop traced for {hard_stop.get('hard_stop_scope') or scope}.",
            event_payload_json=hard_stop,
        )
        if hard_stop.get("id"):
            record_permission_audit(
                s,
                state,
                audit_scope="hard_stop",
                realtime_trace_event_id=event.id,
                hard_stop_event_id=hard_stop["id"],
                audit_summary="Hard stop received highest-priority trace audit.",
                audit_payload_json=hard_stop,
            )
        state["scoped_hard_stop"] = hard_stop
        append_step(
            state,
            step="scoped_hard_stop",
            order=209,
            realtime_trace_event_id=str(event.id),
            hard_stop_event_id=hard_stop.get("id"),
            hard_stop_scope=hard_stop.get("hard_stop_scope") or scope,
            requires_audit=hard_stop.get("requires_audit", True),
        )
        s.commit()
    return state


def _default_channel_id(state: RealtimeAgentState) -> str | None:
    with get_session() as s:
        row = (
            s.execute(
                select(RealtimeSessionChannel.id)
                .where(RealtimeSessionChannel.realtime_session_id == uuid.UUID(state["realtime_session_id"]))
                .order_by(RealtimeSessionChannel.created_at.asc())
                .limit(1)
            ).scalar_one_or_none()
        )
        return str(row) if row else None
