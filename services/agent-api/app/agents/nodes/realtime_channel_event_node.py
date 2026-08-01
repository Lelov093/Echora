"""Trace compatibility-only realtime channel state."""

import uuid

from sqlalchemy import select

from app.agents.state import RealtimeAgentState
from app.agents.nodes.realtime_trace_utils import append_step, record_permission_audit, record_trace_event
from app.db.models import RealtimeChannelStateEvent, RealtimeSessionChannel
from app.services.trace_service import get_session


def realtime_channel_event_node(state: RealtimeAgentState) -> RealtimeAgentState:
    with get_session() as s:
        channels = list(
            s.execute(
                select(RealtimeSessionChannel)
                .where(RealtimeSessionChannel.realtime_session_id == uuid.UUID(state["realtime_session_id"]))
                .order_by(RealtimeSessionChannel.opened_at.asc(), RealtimeSessionChannel.created_at.asc())
            ).scalars()
        )
        recent_events = list(
            s.execute(
                select(RealtimeChannelStateEvent)
                .where(RealtimeChannelStateEvent.realtime_session_id == uuid.UUID(state["realtime_session_id"]))
                .order_by(RealtimeChannelStateEvent.occurred_at.desc())
                .limit(10)
            ).scalars()
        )
        default_channel = channels[0] if channels else None
        summary = {
            "channel_count": len(channels),
            "active_channel_count": len([item for item in channels if item.channel_status == "active"]),
            "default_channel_id": str(default_channel.id) if default_channel else None,
            "recent_event_count": len(recent_events),
        }
        event = record_trace_event(
            s,
            state,
            event_type="channel_state",
            source_channel_id=default_channel.id if default_channel else None,
            event_summary="Realtime channel state traced.",
            event_payload_json={
                **summary,
                "channels": [
                    {
                        "channel_id": str(item.id),
                        "channel_type": item.channel_type,
                        "channel_status": item.channel_status,
                        "transport_type": item.transport_type,
                        "can_send_events": item.can_send_events,
                        "can_receive_actions": item.can_receive_actions,
                    }
                    for item in channels
                ],
            },
        )
        for channel in channels:
            record_permission_audit(
                s,
                state,
                audit_scope="channel",
                realtime_trace_event_id=event.id,
                audit_summary=f"Channel {channel.channel_type} permission posture traced.",
                audit_payload_json={
                    "channel_id": str(channel.id),
                    "can_send_events": channel.can_send_events,
                    "can_receive_actions": channel.can_receive_actions,
                    "transport_type": channel.transport_type,
                },
            )
        state["channel_event_summary"] = summary
        append_step(state, step="realtime_channel_event", order=203, realtime_trace_event_id=str(event.id), **summary)
        s.commit()
    return state
