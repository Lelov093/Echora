"""Isolate the active realtime speaker and honor interruption gates."""

import uuid

from sqlalchemy import select

from app.agents.nodes.realtime_trace_utils import append_step, record_trace_event
from app.agents.state import RealtimeAgentState
from app.db.models import RealtimeCoPresenceParticipant, SpeakerTrace
from app.services.trace_service import get_session
from app.services.turn_taking_service import select_realtime_speaker


def realtime_speaker_turn_node(state: RealtimeAgentState) -> RealtimeAgentState:
    with get_session() as s:
        rows = list(
            s.execute(
                select(RealtimeCoPresenceParticipant)
                .where(RealtimeCoPresenceParticipant.realtime_session_id == uuid.UUID(state["realtime_session_id"]))
                .order_by(RealtimeCoPresenceParticipant.created_at.asc())
            ).scalars()
        )
        selected = select_realtime_speaker(
            [
                {
                    "id": str(item.id),
                    "participant_status": item.participant_status,
                    "participant_role": item.participant_role,
                    "participant_companion_id": str(item.participant_companion_id)
                    if item.participant_companion_id
                    else None,
                    "can_speak": item.can_speak,
                }
                for item in rows
            ],
            state.get("companion_id"),
        )
        speaker = next((item for item in rows if selected and str(item.id) == selected["id"]), None)
        decision = (state.get("realtime_session") or {}).get("realtime_algorithm_decision") or {}
        proactive_allowed = decision.get("proactive_insert_allowed") is True and speaker is not None
        if not proactive_allowed:
            event = record_trace_event(
                s,
                state,
                event_type="speaker_turn",
                event_status="suppressed",
                event_summary=f"No proactive companion turn: {decision.get('reason') or 'speaker_unavailable'}.",
                event_payload_json={
                    "decision": decision.get("decision") or "silence",
                    "reason": decision.get("reason") or "speaker_unavailable",
                    "proactive_insert_allowed": False,
                    "speaker_participant_id": None,
                    "real_stt_tts_enabled": False,
                    "raw_audio_storage_allowed": False,
                },
            )
            state["voice_turn_trace"] = {
                "speaker_trace_id": None,
                "realtime_trace_event_id": str(event.id),
                "decision": decision.get("decision") or "silence",
                "reason": decision.get("reason") or "speaker_unavailable",
                "raw_audio_storage_allowed": False,
            }
            append_step(
                state,
                step="companion_voice_turn",
                order=207,
                realtime_trace_event_id=str(event.id),
                decision=state["voice_turn_trace"]["decision"],
                reason=state["voice_turn_trace"]["reason"],
                speaker_trace_id=None,
            )
            s.commit()
            return state

        event = record_trace_event(
            s,
            state,
            event_type="speaker_turn",
            source_participant_id=speaker.id,
            event_summary="Companion turn approved as text/page readiness only.",
            event_payload_json={
                "real_stt_tts_enabled": False,
                "real_media_enabled": False,
                "transcript_retention_policy": "ephemeral",
                "speaker_participant_id": str(speaker.id),
                "speaker_role": speaker.participant_role,
                "proactive_insert_allowed": True,
            },
        )
        speaker_trace = SpeakerTrace(
            user_id=uuid.UUID(state["user_id"]),
            realtime_trace_event_id=event.id,
            speaker_participant_id=speaker.id,
            speaker_companion_id=speaker.participant_companion_id,
            speaker_trace_status="queued",
            transcript_retention_policy="ephemeral",
            transcript_excerpt_ephemeral=True,
            speaker_payload_json={
                "voice_runtime": "text_page_readiness",
                "no_raw_audio": True,
                "observing_participant_selected": False,
            },
            metadata_={"phase": "core_r13"},
        )
        s.add(speaker_trace)
        s.flush()
        state["voice_turn_trace"] = {
            "speaker_trace_id": str(speaker_trace.id),
            "realtime_trace_event_id": str(event.id),
            "decision": "proactive_insert",
            "transcript_retention_policy": speaker_trace.transcript_retention_policy,
            "raw_audio_storage_allowed": False,
        }
        append_step(
            state,
            step="companion_voice_turn",
            order=207,
            realtime_trace_event_id=str(event.id),
            speaker_trace_id=str(speaker_trace.id),
            decision="proactive_insert",
            transcript_retention_policy="ephemeral",
        )
        s.commit()
    return state
