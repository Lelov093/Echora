"""Trace a compatibility-only companion voice turn without real STT/TTS media."""

import uuid

from sqlalchemy import select

from app.agents.state import RealtimeAgentState
from app.agents.nodes.realtime_trace_utils import append_step, record_trace_event
from app.db.models import RealtimeCoPresenceParticipant, SpeakerTrace
from app.services.trace_service import get_session


def companion_voice_turn_node(state: RealtimeAgentState) -> RealtimeAgentState:
    with get_session() as s:
        speaker = (
            s.execute(
                select(RealtimeCoPresenceParticipant)
                .where(
                    RealtimeCoPresenceParticipant.realtime_session_id == uuid.UUID(state["realtime_session_id"]),
                    RealtimeCoPresenceParticipant.can_speak.is_(True),
                )
                .order_by(RealtimeCoPresenceParticipant.created_at.asc())
                .limit(1)
            ).scalar_one_or_none()
        )
        event = record_trace_event(
            s,
            state,
            event_type="speaker_turn",
            source_participant_id=speaker.id if speaker else None,
            event_summary="Companion voice turn traced as text/page readiness only.",
            event_payload_json={
                "real_stt_tts_enabled": False,
                "transcript_retention_policy": "ephemeral",
                "speaker_participant_id": str(speaker.id) if speaker else None,
            },
        )
        speaker_trace = SpeakerTrace(
            user_id=uuid.UUID(state["user_id"]),
            realtime_trace_event_id=event.id,
            speaker_participant_id=speaker.id if speaker else None,
            speaker_companion_id=speaker.participant_companion_id if speaker else uuid.UUID(state["companion_id"]),
            speaker_trace_status="queued",
            transcript_retention_policy="ephemeral",
            transcript_excerpt_ephemeral=True,
            speaker_payload_json={
                "voice_runtime": "text_page_readiness",
                "no_raw_audio": True,
            },
            metadata_={"implementation_origin": "realtime_trace"},
        )
        s.add(speaker_trace)
        s.flush()
        state["voice_turn_trace"] = {
            "speaker_trace_id": str(speaker_trace.id),
            "realtime_trace_event_id": str(event.id),
            "transcript_retention_policy": speaker_trace.transcript_retention_policy,
            "raw_audio_storage_allowed": False,
        }
        append_step(
            state,
            step="companion_voice_turn",
            order=204,
            realtime_trace_event_id=str(event.id),
            speaker_trace_id=str(speaker_trace.id),
            transcript_retention_policy="ephemeral",
        )
        s.commit()
    return state
