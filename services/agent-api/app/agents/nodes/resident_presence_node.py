"""Trace compatibility-only resident presence and low-interruption posture."""

import uuid

from sqlalchemy import select

from app.agents.state import RealtimeAgentState
from app.agents.nodes.realtime_trace_utils import append_step, record_trace_event
from app.db.models import CompanionResidentStatusEvent, ResidentPresenceEvent
from app.services.trace_service import get_session


def resident_presence_node(state: RealtimeAgentState) -> RealtimeAgentState:
    with get_session() as s:
        status = (
            s.execute(
                select(CompanionResidentStatusEvent)
                .where(
                    CompanionResidentStatusEvent.companion_id == uuid.UUID(state["companion_id"]),
                    CompanionResidentStatusEvent.user_id == uuid.UUID(state["user_id"]),
                )
                .order_by(CompanionResidentStatusEvent.occurred_at.desc(), CompanionResidentStatusEvent.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
        )
        events = list(
            s.execute(
                select(ResidentPresenceEvent)
                .where(ResidentPresenceEvent.realtime_session_id == uuid.UUID(state["realtime_session_id"]))
                .order_by(ResidentPresenceEvent.occurred_at.desc(), ResidentPresenceEvent.created_at.desc())
                .limit(10)
            ).scalars()
        )
        presence = {
            "status_type": status.status_type if status else "available",
            "interruption_level": status.interruption_level if status else "low",
            "allows_unsolicited_presence": bool(status.allows_unsolicited_presence) if status else False,
            "resident_event_count": len(events),
            "low_interruption_default": True,
            "algorithm_decision": (
                (state.get("realtime_session") or {}).get("realtime_algorithm_decision") or {}
            ).get("decision", "silence"),
            "algorithm_reason": (
                (state.get("realtime_session") or {}).get("realtime_algorithm_decision") or {}
            ).get("reason", "not_evaluated"),
            "proactive_insert_allowed": bool(
                (
                    (state.get("realtime_session") or {}).get("realtime_algorithm_decision") or {}
                ).get("proactive_insert_allowed")
            ),
            "real_media_enabled": False,
        }
        event = record_trace_event(
            s,
            state,
            event_type="session_state",
            event_summary="Resident presence posture traced.",
            event_payload_json=presence,
        )
        state["resident_presence"] = presence
        append_step(state, step="resident_presence", order=210, realtime_trace_event_id=str(event.id), **presence)
        s.commit()
    return state
