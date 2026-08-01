"""Enforce an explicit realtime hard stop or load an active one."""

import uuid

from sqlalchemy import or_, select

from app.agents.nodes.realtime_trace_utils import append_step, record_permission_audit, record_trace_event
from app.agents.state import RealtimeAgentState
from app.db.models import ScopedHardStopEvent
from app.services import scoped_hard_stop_service
from app.services.trace_service import get_session


def realtime_hard_stop_gate_node(state: RealtimeAgentState) -> RealtimeAgentState:
    requested_scope = state.get("hard_stop_scope")
    existing = _active_hard_stop(state)
    if existing is None and requested_scope:
        hard_stop = _trigger_requested_stop(state, requested_scope)
    elif existing is not None:
        hard_stop = {
            "id": str(existing.id),
            "hard_stop_scope": existing.hard_stop_scope,
            "hard_stop_status": existing.hard_stop_status,
            "requires_audit": existing.requires_audit,
            "active": True,
        }
    else:
        hard_stop = {
            "id": None,
            "hard_stop_scope": None,
            "hard_stop_status": "clear",
            "requires_audit": False,
            "active": False,
        }
    if hard_stop.get("id"):
        hard_stop["active"] = hard_stop.get("hard_stop_status") == "active"

    with get_session() as s:
        event = record_trace_event(
            s,
            state,
            event_type="hard_stop",
            event_status="suppressed" if hard_stop["active"] else "recorded",
            event_summary=(
                f"Scoped hard stop active for {hard_stop.get('hard_stop_scope')}."
                if hard_stop["active"]
                else "No active scoped hard stop."
            ),
            event_payload_json=hard_stop,
        )
        if hard_stop.get("id"):
            record_permission_audit(
                s,
                state,
                audit_scope="hard_stop",
                realtime_trace_event_id=event.id,
                hard_stop_event_id=hard_stop["id"],
                audit_summary="Hard stop received highest-priority realtime gate audit.",
                audit_payload_json=hard_stop,
            )
        state["scoped_hard_stop"] = hard_stop
        append_step(
            state,
            step="scoped_hard_stop",
            order=205,
            realtime_trace_event_id=str(event.id),
            hard_stop_event_id=hard_stop.get("id"),
            hard_stop_scope=hard_stop.get("hard_stop_scope"),
            active=hard_stop["active"],
            requires_audit=hard_stop.get("requires_audit", False),
        )
        s.commit()
    return state


def _active_hard_stop(state: RealtimeAgentState):
    user_id = uuid.UUID(state["user_id"])
    session_id = uuid.UUID(state["realtime_session_id"])
    companion_id = uuid.UUID(state["companion_id"])
    channel_id = _to_uuid(state.get("hard_stop_target_id") or state.get("default_channel_id"))
    with get_session() as s:
        return (
            s.execute(
                select(ScopedHardStopEvent)
                .where(
                    ScopedHardStopEvent.user_id == user_id,
                    ScopedHardStopEvent.hard_stop_status == "active",
                    ScopedHardStopEvent.released_at.is_(None),
                    or_(
                        ScopedHardStopEvent.hard_stop_scope == "all_realtime",
                        (
                            (ScopedHardStopEvent.hard_stop_scope == "session")
                            & (ScopedHardStopEvent.realtime_session_id == session_id)
                        ),
                        (
                            (ScopedHardStopEvent.hard_stop_scope == "companion")
                            & (ScopedHardStopEvent.companion_id == companion_id)
                        ),
                        (
                            (ScopedHardStopEvent.hard_stop_scope == "channel")
                            & (ScopedHardStopEvent.channel_id == channel_id)
                        ),
                    ),
                )
                .order_by(ScopedHardStopEvent.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
        )


def _trigger_requested_stop(state: RealtimeAgentState, scope: str) -> dict:
    payload = {"stop_reason": "Realtime graph hard stop trace checkpoint"}
    if scope == "session":
        payload["realtime_session_id"] = state["realtime_session_id"]
    elif scope == "companion":
        payload["companion_id"] = state["companion_id"]
    elif scope == "sensor":
        payload["context_event_id"] = state.get("hard_stop_target_id")
    elif scope == "all_realtime":
        pass
    else:
        scope = "channel"
        payload["channel_id"] = state.get("hard_stop_target_id") or state.get("default_channel_id")
    result = scoped_hard_stop_service.trigger_scoped_hard_stop(
        uuid.UUID(state["user_id"]),
        {"hard_stop_scope": scope, **payload},
    )
    return (result or {}).get("hard_stop") or {}


def _to_uuid(value: str | None) -> uuid.UUID | None:
    return uuid.UUID(value) if value else None
