"""Trace compatibility-only realtime participant awareness and permissions."""

import uuid

from sqlalchemy import select

from app.agents.state import RealtimeAgentState
from app.agents.nodes.realtime_trace_utils import append_step, record_permission_audit, record_trace_event
from app.db.models import ParticipantEventTrace, RealtimeCoPresenceParticipant
from app.services.trace_service import get_session


def participant_awareness_realtime_node(state: RealtimeAgentState) -> RealtimeAgentState:
    with get_session() as s:
        participants = list(
            s.execute(
                select(RealtimeCoPresenceParticipant)
                .where(RealtimeCoPresenceParticipant.realtime_session_id == uuid.UUID(state["realtime_session_id"]))
                .order_by(RealtimeCoPresenceParticipant.joined_at.asc(), RealtimeCoPresenceParticipant.created_at.asc())
            ).scalars()
        )
        awareness = {
            "participant_count": len(participants),
            "active_count": len([item for item in participants if item.participant_status == "active"]),
            "observing_companion_count": len([item for item in participants if item.participant_role == "observing_companion"]),
            "memory_enabled_count": len([item for item in participants if item.can_remember]),
            "participants": [],
        }
        event = record_trace_event(
            s,
            state,
            event_type="participant_permission",
            event_summary="Realtime participant permissions reviewed.",
            event_payload_json={
                "participant_count": awareness["participant_count"],
                "observing_companion_memory_default": "blocked",
            },
        )
        for participant in participants:
            item = {
                "participant_id": str(participant.id),
                "participant_type": participant.participant_type,
                "participant_role": participant.participant_role,
                "participant_status": participant.participant_status,
                "can_listen": participant.can_listen,
                "can_speak": participant.can_speak,
                "can_observe": participant.can_observe,
                "can_remember": participant.can_remember,
                "can_receive_transcript": participant.can_receive_transcript,
            }
            awareness["participants"].append(item)
            for action, allowed in (
                ("listen", participant.can_listen),
                ("speak", participant.can_speak),
                ("observe", participant.can_observe),
                ("remember", participant.can_remember),
                ("receive_transcript", participant.can_receive_transcript),
            ):
                s.add(
                    ParticipantEventTrace(
                        user_id=uuid.UUID(state["user_id"]),
                        realtime_trace_event_id=event.id,
                        participant_id=participant.id,
                        permission_action=action,
                        permission_allowed=bool(allowed),
                        review_required=True,
                        permission_snapshot_json={
                            "participant_role": participant.participant_role,
                            "observing_companion_memory_blocked": participant.participant_role == "observing_companion",
                        },
                        metadata_={"implementation_origin": "realtime_trace"},
                    )
                )
            record_permission_audit(
                s,
                state,
                audit_scope="participant",
                realtime_trace_event_id=event.id,
                participant_id=participant.id,
                audit_summary=f"Participant {participant.participant_role} permissions traced.",
                audit_payload_json=item,
            )
        state["participant_awareness"] = awareness
        append_step(
            state,
            step="participant_awareness_realtime",
            order=202,
            realtime_trace_event_id=str(event.id),
            participant_count=awareness["participant_count"],
            observing_companion_count=awareness["observing_companion_count"],
            memory_enabled_count=awareness["memory_enabled_count"],
        )
        s.commit()
    return state
