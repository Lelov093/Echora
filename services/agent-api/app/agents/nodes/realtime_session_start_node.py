"""Start a compatibility-only realtime graph and trace its session."""

import uuid

from sqlalchemy import select

from app.agents.state import RealtimeAgentState
from app.agents.nodes.realtime_trace_utils import append_step, now, public_row, record_trace_event
from app.db.models import (
    RealtimeCoPresenceParticipant,
    RealtimeCoPresenceSession,
    RealtimeSessionChannel,
    RealtimeTraceSession,
    TraceRun,
)
from app.services.trace_service import get_session


def realtime_session_start_node(state: RealtimeAgentState) -> RealtimeAgentState:
    with get_session() as s:
        realtime_session = s.get(RealtimeCoPresenceSession, uuid.UUID(state["realtime_session_id"]))
        if realtime_session is None:
            state.setdefault("errors", []).append({"step": "realtime_session_start", "error": "session_not_found"})
            append_step(state, step="realtime_session_start", order=201, status="failed", reason="session_not_found")
            return state

        companion_id = realtime_session.active_companion_id or _first_companion_id(s, realtime_session.id)
        if companion_id is None:
            state.setdefault("errors", []).append({"step": "realtime_session_start", "error": "companion_required"})
            append_step(state, step="realtime_session_start", order=201, status="failed", reason="companion_required")
            return state

        trace_run = TraceRun(
            user_id=realtime_session.user_id,
            companion_id=companion_id,
            conversation_id=realtime_session.originating_conversation_id,
            agent_graph_name="realtime_session_graph",
            input_summary=realtime_session.session_title or "Realtime co-presence session",
            status="started",
            realtime_session_id=realtime_session.id,
            metadata_={
                "realtime_context": {
                    "graph_version": "v5_realtime",
                    "algorithm_version": "core-r13-v1",
                    "session_status": realtime_session.session_status,
                    "real_media_enabled": False,
                }
            },
        )
        s.add(trace_run)
        s.flush()

        realtime_trace = RealtimeTraceSession(
            user_id=realtime_session.user_id,
            realtime_session_id=realtime_session.id,
            co_presence_session_id=realtime_session.co_presence_session_id,
            trace_run_id=trace_run.id,
            trace_status="recording",
            trace_level="key_events",
            raw_capture_policy="disabled",
            raw_audio_storage_allowed=False,
            raw_screen_storage_allowed=False,
            raw_video_storage_allowed=False,
            redaction_required=True,
            retention_policy="review_summary_only",
            trace_summary="Realtime co-presence graph trace started.",
            policy_snapshot_json={
                "raw_capture_policy": "disabled",
                "observing_companion_memory": "disabled_by_default",
                "hard_stop_priority": "highest",
                "real_media_enabled": False,
                "supported_signals": ["text", "transcript_summary", "event", "channel", "permission"],
            },
            started_at=now(),
            metadata_={"implementation_origin": "realtime_trace"},
        )
        s.add(realtime_trace)
        s.flush()

        trace_run.realtime_trace_session_id = realtime_trace.id
        s.flush()

        state["user_id"] = str(realtime_session.user_id)
        state["companion_id"] = str(companion_id)
        state["trace_run_id"] = str(trace_run.id)
        state["realtime_trace_session_id"] = str(realtime_trace.id)
        state["realtime_session"] = public_row(
            realtime_session,
            (
                "user_id",
                "co_presence_session_id",
                "active_companion_id",
                "session_status",
                "session_source",
                "default_transport",
                "permission_snapshot_json",
                "boundary_snapshot_json",
                "runtime_state_json",
            ),
        )

        participants = list(
            s.execute(
                select(RealtimeCoPresenceParticipant)
                .where(RealtimeCoPresenceParticipant.realtime_session_id == realtime_session.id)
                .order_by(RealtimeCoPresenceParticipant.joined_at.asc(), RealtimeCoPresenceParticipant.created_at.asc())
            ).scalars()
        )
        channels = list(
            s.execute(
                select(RealtimeSessionChannel)
                .where(RealtimeSessionChannel.realtime_session_id == realtime_session.id)
                .order_by(RealtimeSessionChannel.opened_at.asc(), RealtimeSessionChannel.created_at.asc())
            ).scalars()
        )
        state["realtime_participants"] = [
            public_row(
                item,
                (
                    "participant_type",
                    "participant_role",
                    "participant_status",
                    "participant_user_id",
                    "participant_companion_id",
                    "can_listen",
                    "can_speak",
                    "can_observe",
                    "can_remember",
                    "can_receive_transcript",
                    "permission_snapshot_json",
                ),
            )
            for item in participants
        ]
        state["realtime_channels"] = [
            public_row(
                item,
                (
                    "channel_type",
                    "channel_status",
                    "transport_type",
                    "is_default_event_stream",
                    "can_send_events",
                    "can_receive_actions",
                    "permission_snapshot_json",
                ),
            )
            for item in channels
        ]
        if channels:
            state["default_channel_id"] = str(channels[0].id)

        event = record_trace_event(
            s,
            state,
            event_type="session_state",
            event_summary="Realtime session entered graph trace.",
            event_payload_json={
                "session_status": realtime_session.session_status,
                "participant_count": len(participants),
                "channel_count": len(channels),
                "real_media_enabled": False,
                "real_audio_enabled": False,
                "real_video_enabled": False,
                "continuous_screen_state_enabled": False,
            },
        )
        append_step(
            state,
            step="realtime_session_start",
            order=201,
            realtime_trace_event_id=str(event.id),
            realtime_trace_session_id=str(realtime_trace.id),
            participant_count=len(participants),
            channel_count=len(channels),
            algorithm_version="core-r13-v1",
            real_media_enabled=False,
        )
        s.commit()
    return state


def _first_companion_id(s, realtime_session_id: uuid.UUID) -> uuid.UUID | None:
    row = (
        s.execute(
            select(RealtimeCoPresenceParticipant.participant_companion_id)
            .where(
                RealtimeCoPresenceParticipant.realtime_session_id == realtime_session_id,
                RealtimeCoPresenceParticipant.participant_companion_id.is_not(None),
            )
            .limit(1)
        ).scalar_one_or_none()
    )
    return row
