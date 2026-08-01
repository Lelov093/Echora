"""Finalize compatibility-only realtime trace, replay, and redaction."""

import uuid

from sqlalchemy import select

from app.agents.state import RealtimeAgentState
from app.agents.nodes.realtime_trace_utils import append_step, now, record_trace_event
from app.db.models import (
    RedactionEvent,
    RealtimeReplay,
    RealtimeReplaySegment,
    RealtimeTraceEvent,
    RealtimeTraceSession,
    TraceRun,
    TraceStep,
)
from app.services.trace_service import get_session


def realtime_trace_logging_node(state: RealtimeAgentState) -> RealtimeAgentState:
    with get_session() as s:
        trace_run = s.get(TraceRun, uuid.UUID(state["trace_run_id"]))
        realtime_trace = s.get(RealtimeTraceSession, uuid.UUID(state["realtime_trace_session_id"]))
        if trace_run is None or realtime_trace is None:
            state.setdefault("errors", []).append({"step": "realtime_trace_logging", "error": "trace_missing"})
            append_step(state, step="realtime_trace_logging", order=210, status="failed", reason="trace_missing")
            return state

        redaction_event = record_trace_event(
            s,
            state,
            event_type="redaction",
            event_summary="Realtime trace redaction gate recorded.",
            event_payload_json={
                "redaction_required": True,
                "redaction_policy": "summary_only",
                "raw_media_included": False,
            },
        )
        redaction = RedactionEvent(
            user_id=uuid.UUID(state["user_id"]),
            realtime_trace_event_id=redaction_event.id,
            redaction_status="pending",
            redaction_policy="summary_only",
            audit_required=True,
            redaction_summary="Realtime replay and trace remain summary-only pending review.",
            redaction_payload_json={"raw_audio": False, "raw_screen": False, "raw_video": False},
            metadata_={"implementation_origin": "realtime_trace"},
        )
        s.add(redaction)
        s.flush()
        state.setdefault("redaction_event_ids", []).append(str(redaction.id))

        events = list(
            s.execute(
                select(RealtimeTraceEvent)
                .where(RealtimeTraceEvent.realtime_trace_session_id == realtime_trace.id)
                .order_by(RealtimeTraceEvent.occurred_at.asc(), RealtimeTraceEvent.created_at.asc())
            ).scalars()
        )
        replay = RealtimeReplay(
            user_id=uuid.UUID(state["user_id"]),
            realtime_trace_session_id=realtime_trace.id,
            realtime_session_id=uuid.UUID(state["realtime_session_id"]),
            replay_status="ready",
            replay_scope="key_events",
            includes_transcript_summary=True,
            includes_key_events=True,
            includes_raw_audio=False,
            includes_raw_screen=False,
            includes_raw_video=False,
            redaction_required=True,
            replay_summary="Summary-only replay for realtime co-presence graph trace.",
            replay_payload_json={
                "event_count": len(events),
                "redaction_event_id": str(redaction.id),
                "hard_stop_event_id": (state.get("scoped_hard_stop") or {}).get("id"),
            },
            metadata_={"implementation_origin": "realtime_trace"},
        )
        s.add(replay)
        s.flush()

        for index, event in enumerate(events):
            segment_type = _segment_type(event.event_type)
            segment = RealtimeReplaySegment(
                user_id=uuid.UUID(state["user_id"]),
                realtime_replay_id=replay.id,
                source_trace_event_id=event.id,
                segment_type=segment_type,
                segment_order=index,
                segment_status="ready",
                segment_summary=event.event_summary,
                raw_segment_storage_allowed=False,
                redaction_required=True,
                segment_payload_json={
                    "event_type": event.event_type,
                    "event_status": event.event_status,
                    "summary_only": True,
                },
                metadata_={"implementation_origin": "realtime_trace"},
            )
            s.add(segment)
            s.flush()
            state.setdefault("replay_segment_ids", []).append(str(segment.id))

        summary = {
            "graph_version": "v5_realtime",
            "algorithm_version": "core-r13-v1",
            "realtime_session_id": state["realtime_session_id"],
            "realtime_trace_session_id": state["realtime_trace_session_id"],
            "event_count": len(events),
            "participant_audit_count": len(state.get("permission_audit_event_ids", [])),
            "memory_gate_count": len(state.get("memory_gate_trace_ids", [])),
            "redaction_required": True,
            "replay_id": str(replay.id),
            "hard_stop_event_id": (state.get("scoped_hard_stop") or {}).get("id"),
            "interruption_decision": (
                (state.get("realtime_session") or {}).get("realtime_algorithm_decision") or {}
            ).get("decision"),
            "interruption_reason": (
                (state.get("realtime_session") or {}).get("realtime_algorithm_decision") or {}
            ).get("reason"),
            "real_media_enabled": False,
        }
        state["realtime_replay"] = {
            "id": str(replay.id),
            "replay_status": replay.replay_status,
            "replay_scope": replay.replay_scope,
            "includes_raw_audio": replay.includes_raw_audio,
            "includes_raw_screen": replay.includes_raw_screen,
            "includes_raw_video": replay.includes_raw_video,
            "segment_count": len(state.get("replay_segment_ids", [])),
        }
        state["redaction"] = {
            "id": str(redaction.id),
            "redaction_status": redaction.redaction_status,
            "redaction_policy": redaction.redaction_policy,
            "audit_required": redaction.audit_required,
        }
        state["realtime_trace_summary"] = summary
        append_step(state, step="realtime_trace_logging", order=211, realtime_trace_event_id=str(redaction_event.id), **summary)

        for step_data in state.get("trace_steps", []):
            step_name = step_data.get("step", "unknown")
            ts = TraceStep(
                trace_run_id=trace_run.id,
                step_name=step_name,
                step_order=step_data.get("order", 0),
                status=step_data.get("status", "completed"),
                decision=step_data.get("decision"),
                output_json={k: v for k, v in step_data.items() if k not in ("step", "order", "status")},
                started_at=now(),
                completed_at=now(),
                realtime_copresence_json={
                    "realtime_session": state.get("realtime_session") or {},
                    "channel_event_summary": state.get("channel_event_summary") or {},
                    "resident_presence": state.get("resident_presence") or {},
                    "scoped_hard_stop": state.get("scoped_hard_stop") or {},
                    "realtime_algorithm_decision": (
                        state.get("realtime_session") or {}
                    ).get("realtime_algorithm_decision")
                    or {},
                    "realtime_latent_state": (
                        state.get("realtime_session") or {}
                    ).get("realtime_latent_state")
                    or {},
                },
                participant_permission_json={
                    "participant_awareness": state.get("participant_awareness") or {},
                    "multimodal_permission": state.get("multimodal_permission") or {},
                    "permission_audit_event_ids": state.get("permission_audit_event_ids", []),
                },
                realtime_memory_gate_json={
                    "realtime_memory_gate": state.get("realtime_memory_gate") or {},
                    "shared_moment_candidate": state.get("shared_moment_candidate") or {},
                    "memory_gate_trace_ids": state.get("memory_gate_trace_ids", []),
                },
                metadata_={"implementation_origin": "realtime_trace"},
            )
            s.add(ts)

        realtime_trace.trace_status = "completed"
        realtime_trace.ended_at = now()
        realtime_trace.trace_summary = "Realtime graph trace completed with summary-only replay."
        trace_run.status = "failed" if state.get("errors") else "completed"
        trace_run.output_summary = "Realtime co-presence graph trace completed."
        metadata = dict(trace_run.metadata_ or {})
        metadata["realtime_context"] = summary
        trace_run.metadata_ = metadata
        s.commit()
    return state


def _segment_type(event_type: str) -> str:
    if event_type == "participant_permission":
        return "permission_audit"
    if event_type == "memory_gate":
        return "memory_gate"
    if event_type == "speaker_turn":
        return "transcript_excerpt"
    if event_type == "redaction":
        return "summary"
    return "key_event"
