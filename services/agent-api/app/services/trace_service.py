"""Trace service layer with V3 compatibility and Companion Reoriented views."""

import uuid
from typing import Any

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import (
    HardStopAuditEvent,
    Memory,
    MemoryGateTrace,
    ParticipantEventTrace,
    PermissionAuditEvent,
    RedactionEvent,
    RealtimeReplay,
    RealtimeReplaySegment,
    RealtimeTraceEvent,
    RealtimeTraceSession,
    SpeakerTrace,
    TraceRun,
    TraceStep,
)
from app.schemas.companion_trace import (
    CompanionTraceDetail,
    CompanionTraceSection,
    CompanionTraceSummary,
)

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(settings.DATABASE_URL, echo=False)
    return _engine


def get_session() -> Session:
    return Session(_get_engine())


def list_traces(
    companion_id: uuid.UUID | None = None,
    conversation_id: uuid.UUID | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    with get_session() as s:
        stmt = select(TraceRun)
        if companion_id:
            stmt = stmt.where(TraceRun.companion_id == companion_id)
        if conversation_id:
            stmt = stmt.where(TraceRun.conversation_id == conversation_id)
        total = s.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
        stmt = stmt.order_by(TraceRun.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        items = list(s.execute(stmt).scalars().all())
        return {"items": items, "total": total}


def get_trace_detail(trace_run_id: uuid.UUID) -> dict | None:
    with get_session() as s:
        trace_run = s.get(TraceRun, trace_run_id)
        if not trace_run:
            return None
        steps = list(
            s.execute(
                select(TraceStep)
                .where(TraceStep.trace_run_id == trace_run_id)
                .order_by(TraceStep.step_order)
            ).scalars().all()
        )
        all_memory_ids = list(set((trace_run.retrieved_memory_ids or []) + (trace_run.selected_memory_ids or [])))
        used_memories = _resolve_memories(s, all_memory_ids)
        companion_context = _companion_trace_dict(s, trace_run, steps)
        return {
            "trace_run": _tr_dict(trace_run),
            "steps": [_ts_dict(step) for step in steps],
            "used_memories": used_memories,
            "provider_mode": trace_run.model_provider or "unrecorded",
            "embedding_mode": "unrecorded",
            "execution_signals": _execution_signals_dict(trace_run, steps),
            "companion_context": companion_context,
            "realtime_trace": _realtime_trace_dict(s, trace_run, steps),
        }


def list_conversation_traces(conversation_id: uuid.UUID, page: int = 1, page_size: int = 20) -> dict:
    return list_traces(conversation_id=conversation_id, page=page, page_size=page_size)


def get_realtime_trace_detail(trace_run_id: uuid.UUID) -> dict | None:
    with get_session() as s:
        trace_run = s.get(TraceRun, trace_run_id)
        if not trace_run:
            return None
        steps = list(
            s.execute(
                select(TraceStep)
                .where(TraceStep.trace_run_id == trace_run_id)
                .order_by(TraceStep.step_order)
            ).scalars().all()
        )
        return _realtime_trace_dict(s, trace_run, steps)


def _resolve_memories(s: Session, memory_ids: list[uuid.UUID]) -> list[dict]:
    if not memory_ids:
        return []
    rows = s.execute(select(Memory).where(Memory.id.in_(memory_ids))).scalars().all()
    return [{"id": str(row.id), "summary": row.summary, "content": row.content} for row in rows]


def _tr_dict(trace_run: TraceRun) -> dict:
    return {
        "id": str(trace_run.id),
        "conversation_id": str(trace_run.conversation_id) if trace_run.conversation_id else None,
        "agent_graph_name": trace_run.agent_graph_name,
        "model_provider": trace_run.model_provider,
        "model_name": trace_run.model_name,
        "input_summary": trace_run.input_summary,
        "output_summary": trace_run.output_summary,
        "status": trace_run.status,
        "elapsed_ms": trace_run.elapsed_ms,
        "retrieved_memory_ids": [str(item) for item in (trace_run.retrieved_memory_ids or [])],
        "selected_memory_ids": [str(item) for item in (trace_run.selected_memory_ids or [])],
        "generated_memory_candidate_ids": [str(item) for item in (trace_run.generated_memory_candidate_ids or [])],
        "generated_growth_candidate_ids": [str(item) for item in (trace_run.generated_growth_candidate_ids or [])],
        "generated_presence_opportunity_ids": [str(item) for item in (trace_run.generated_presence_opportunity_ids or [])],
        "tool_run_ids": _string_ids(trace_run.tool_run_ids),
        "file_context_usage_ids": _string_ids(trace_run.file_context_usage_ids),
        "evidence_sufficiency_event_ids": _string_ids(trace_run.evidence_sufficiency_event_ids),
        "memory_reranker_run_ids": _string_ids(trace_run.memory_reranker_run_ids),
        "presence_policy_run_ids": _string_ids(trace_run.presence_policy_run_ids),
        "bad_case_signal_ids": _string_ids(trace_run.bad_case_signal_ids),
        "evaluation_signal_ids": _string_ids(trace_run.evaluation_signal_ids),
        "llm_call_record_ids": _string_ids(trace_run.llm_call_record_ids),
        "execution_signal_summary": trace_run.execution_signal_summary or {},
        "companion_context_summary": _stored_companion_context(trace_run),
        "realtime_trace_summary": _stored_realtime_context(trace_run),
        "realtime_session_id": str(trace_run.realtime_session_id) if trace_run.realtime_session_id else None,
        "realtime_trace_session_id": str(trace_run.realtime_trace_session_id) if trace_run.realtime_trace_session_id else None,
        "metadata": trace_run.metadata_ or {},
        "created_at": trace_run.created_at.isoformat() if trace_run.created_at else None,
    }


def _ts_dict(trace_step: TraceStep) -> dict:
    summary = ""
    if isinstance(trace_step.output_json, dict):
        summary = trace_step.output_json.get("summary", trace_step.output_json.get("reason", ""))
    return {
        "id": str(trace_step.id),
        "name": trace_step.step_name,
        "order": trace_step.step_order,
        "step_name": trace_step.step_name,
        "step_order": trace_step.step_order,
        "status": trace_step.status,
        "decision": trace_step.decision,
        "summary": str(summary)[:200] if summary else None,
        "score_json": trace_step.score_json,
        "elapsed_ms": trace_step.elapsed_ms,
        "output_json": trace_step.output_json if isinstance(trace_step.output_json, dict) else {},
        "tool_json": trace_step.tool_json or {},
        "file_context_json": trace_step.file_context_json or {},
        "evidence_json": trace_step.evidence_json or {},
        "reranker_json": trace_step.reranker_json or {},
        "presence_policy_json": trace_step.presence_policy_json or {},
        "bad_case_signal_json": trace_step.bad_case_signal_json or {},
        "evaluation_signal_json": trace_step.evaluation_signal_json or {},
        "provider_json": trace_step.provider_json or {},
        "outdated_memory_json": trace_step.outdated_memory_json or {},
        "growth_consistency_json": trace_step.growth_consistency_json or {},
        "realtime_copresence_json": trace_step.realtime_copresence_json or {},
        "participant_permission_json": trace_step.participant_permission_json or {},
        "realtime_memory_gate_json": trace_step.realtime_memory_gate_json or {},
    }


def _execution_signals_dict(trace_run: TraceRun, steps: list[TraceStep]) -> dict:
    return {
        "summary": trace_run.execution_signal_summary or {},
        "signals": {
            "tool_run_ids": _string_ids(trace_run.tool_run_ids),
            "file_context_usage_ids": _string_ids(trace_run.file_context_usage_ids),
            "evidence_sufficiency_event_ids": _string_ids(trace_run.evidence_sufficiency_event_ids),
            "memory_reranker_run_ids": _string_ids(trace_run.memory_reranker_run_ids),
            "presence_policy_run_ids": _string_ids(trace_run.presence_policy_run_ids),
            "bad_case_signal_ids": _string_ids(trace_run.bad_case_signal_ids),
            "evaluation_signal_ids": _string_ids(trace_run.evaluation_signal_ids),
            "llm_call_record_ids": _string_ids(trace_run.llm_call_record_ids),
        },
        "step_sections": [
            {
                "step_name": step.step_name,
                "tool": step.tool_json or {},
                "file_context": step.file_context_json or {},
                "evidence": step.evidence_json or {},
                "reranker": step.reranker_json or {},
                "presence_policy": step.presence_policy_json or {},
                "bad_case": step.bad_case_signal_json or {},
                "evaluation": step.evaluation_signal_json or {},
                "provider": step.provider_json or {},
                "outdated_memory": step.outdated_memory_json or {},
                "growth_consistency": step.growth_consistency_json or {},
            }
            for step in steps
        ],
    }


def _companion_trace_dict(s: Session, trace_run: TraceRun, steps: list[TraceStep]) -> dict:
    companion_identity_step = _step_by_name(steps, "companion_identity_activation")
    co_presence_step = _step_by_name(steps, "co_presence_context")
    awareness_step = _step_by_name(steps, "participant_awareness")
    shared_scene_step = _step_by_name(steps, "shared_scene_context")
    memory_scope_step = _step_by_name(steps, "companion_memory_scope")
    shared_memory_step = _step_by_name(steps, "shared_episodic_memory_candidate")
    cross_boundary_step = _step_by_name(steps, "cross_companion_memory_boundary")
    persona_guard_step = _step_by_name(steps, "persona_guard")
    mutual_presence_step = _step_by_name(steps, "mutual_presence_policy")
    delegated_execution_step = _step_by_name(steps, "delegated_execution_planning")
    response_generation_step = _step_by_name(steps, "response_generation")

    companion_context = _stored_companion_context(trace_run)
    cross_pending = int((cross_boundary_step.output_json or {}).get("pending_review_count", 0)) if cross_boundary_step else 0
    shared_review_required = bool(companion_context.get("shared_memory_candidate_count", 0) or cross_pending)
    persona_status = companion_context.get("persona_guard_status")

    summary = CompanionTraceSummary(
        trace_run_id=trace_run.id,
        narrative_summary=_narrative_summary(
            trace_run=trace_run,
            companion_context=companion_context,
            companion_identity_step=companion_identity_step,
            co_presence_step=co_presence_step,
            shared_scene_step=shared_scene_step,
            cross_pending=cross_pending,
        ),
        companion_consistency_score=_consistency_score(persona_status),
        co_presence_boundary_ok=persona_status != "blocked" and cross_pending == 0,
        shared_memory_review_required=shared_review_required,
        metadata={
            **companion_context,
            "provider": trace_run.model_provider,
            "model_name": trace_run.model_name,
        },
    )
    detail = CompanionTraceDetail(
        summary=summary,
        companion_identity_trace=_section(
            companion_identity_step,
            summary="Resolved the active companion identity for this run.",
            data_keys=("companion_name",),
        ),
        persona_profile_trace=_section(
            companion_identity_step,
            summary="Resolved persona and presence-style context.",
            data_keys=("presence_style",),
        ),
        relationship_contract_trace=_section(
            companion_identity_step,
            summary="Resolved relationship contract and visibility posture.",
            data_keys=("relationship_role", "global_memory_read_scope"),
        ),
        co_presence_session_trace=_section(
            co_presence_step,
            summary="Loaded co-presence session context for the conversation.",
            data_keys=("co_presence_session_id", "participant_count", "session_status"),
        ),
        participant_awareness_trace=_section(
            awareness_step,
            summary="Summarized active participants, observers, and awareness visibility.",
            data_keys=("participant_count", "active_companion_count", "observing_companion_count"),
        ),
        shared_scene_trace=_section(
            shared_scene_step,
            summary="Loaded shared scene context and experience count.",
            data_keys=("shared_scene_id", "scene_status", "event_count", "shared_experience_count"),
        ),
        companion_memory_scope_trace=_section(
            memory_scope_step,
            summary="Explained the companion-private memory scope and global visibility boundary.",
            data_keys=("scope_type", "default_write_policy", "global_memory_read_scope", "visible_memory_count"),
        ),
        shared_memory_candidate_trace=_section(
            shared_memory_step,
            summary="Explained how co-presence experiences became review-gated shared memory candidates.",
            data_keys=("shared_memory_candidate_count", "from_shared_scene_count", "from_memory_candidate_count"),
        ),
        cross_companion_boundary_trace=_section(
            cross_boundary_step,
            summary="Explained cross-companion memory review pressure and boundary state.",
            data_keys=("review_count", "pending_review_count"),
        ),
        persona_guard_trace=_section(
            persona_guard_step,
            summary="Explained persona drift and private-memory leakage checks for this run.",
            data_keys=("check_status", "drift_risk_level", "requires_review", "blocks_auto_apply"),
        ),
        mutual_presence_trace=_section(
            mutual_presence_step,
            summary="Explained mutual-presence surface selection and silence policy.",
            data_keys=("presence_opportunity_id", "selected_surface", "policy_run_id"),
        ),
        delegated_execution_trace=_delegated_execution_trace_section(s, delegated_execution_step),
        provider_trace=_provider_trace_section(trace_run, response_generation_step),
        tool_file_evidence_trace=_tool_file_evidence_trace_section(trace_run, steps),
    )
    return detail.model_dump(mode="json")


def _stored_companion_context(trace_run: TraceRun) -> dict[str, Any]:
    metadata = trace_run.metadata_ or {}
    return dict(
        metadata.get("companion_context")
        or metadata.get("phase4_reoriented")
        or {}
    )


def _stored_realtime_context(trace_run: TraceRun) -> dict[str, Any]:
    metadata = trace_run.metadata_ or {}
    return dict(
        metadata.get("realtime_context")
        or metadata.get("phase5_realtime")
        or {}
    )


def _realtime_trace_dict(s: Session, trace_run: TraceRun, steps: list[TraceStep]) -> dict:
    realtime_trace = None
    if trace_run.realtime_trace_session_id:
        realtime_trace = s.get(RealtimeTraceSession, trace_run.realtime_trace_session_id)
    events = []
    participant_event_traces = []
    speaker_traces = []
    permission_audits = []
    memory_gate_traces = []
    replay = None
    replay_segments = []
    redactions = []
    hard_stop_audits = []

    if realtime_trace:
        events = list(
            s.execute(
                select(RealtimeTraceEvent)
                .where(RealtimeTraceEvent.realtime_trace_session_id == realtime_trace.id)
                .order_by(RealtimeTraceEvent.occurred_at.asc(), RealtimeTraceEvent.created_at.asc())
            ).scalars().all()
        )
        event_ids = [item.id for item in events]
        if event_ids:
            participant_event_traces = list(
                s.execute(
                    select(ParticipantEventTrace)
                    .where(ParticipantEventTrace.realtime_trace_event_id.in_(event_ids))
                    .order_by(ParticipantEventTrace.created_at.asc())
                ).scalars().all()
            )
            speaker_traces = list(
                s.execute(
                    select(SpeakerTrace)
                    .where(SpeakerTrace.realtime_trace_event_id.in_(event_ids))
                    .order_by(SpeakerTrace.created_at.asc())
                ).scalars().all()
            )
            redactions = list(
                s.execute(
                    select(RedactionEvent)
                    .where(RedactionEvent.realtime_trace_event_id.in_(event_ids))
                    .order_by(RedactionEvent.created_at.asc())
                ).scalars().all()
            )
        permission_audits = list(
            s.execute(
                select(PermissionAuditEvent)
                .where(PermissionAuditEvent.realtime_trace_session_id == realtime_trace.id)
                .order_by(PermissionAuditEvent.occurred_at.asc(), PermissionAuditEvent.created_at.asc())
            ).scalars().all()
        )
        memory_gate_traces = list(
            s.execute(
                select(MemoryGateTrace)
                .where(MemoryGateTrace.realtime_trace_session_id == realtime_trace.id)
                .order_by(MemoryGateTrace.created_at.asc())
            ).scalars().all()
        )
        replay = (
            s.execute(
                select(RealtimeReplay)
                .where(RealtimeReplay.realtime_trace_session_id == realtime_trace.id)
                .order_by(RealtimeReplay.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
        )
        if replay:
            replay_segments = list(
                s.execute(
                    select(RealtimeReplaySegment)
                    .where(RealtimeReplaySegment.realtime_replay_id == replay.id)
                    .order_by(RealtimeReplaySegment.segment_order.asc())
                ).scalars().all()
            )
            segment_ids = [item.id for item in replay_segments]
            if segment_ids:
                redactions.extend(
                    list(
                        s.execute(
                            select(RedactionEvent)
                            .where(RedactionEvent.realtime_replay_segment_id.in_(segment_ids))
                            .order_by(RedactionEvent.created_at.asc())
                        ).scalars().all()
                    )
                )
        hard_stop_ids = [item.hard_stop_event_id for item in permission_audits if item.hard_stop_event_id]
        if hard_stop_ids:
            hard_stop_audits = list(
                s.execute(
                    select(HardStopAuditEvent)
                    .where(HardStopAuditEvent.hard_stop_event_id.in_(hard_stop_ids))
                    .order_by(HardStopAuditEvent.occurred_at.asc(), HardStopAuditEvent.created_at.asc())
                ).scalars().all()
            )

    event_type_counts: dict[str, int] = {}
    for event in events:
        event_type_counts[event.event_type] = event_type_counts.get(event.event_type, 0) + 1
    summary = {
        **_stored_realtime_context(trace_run),
        "trace_run_id": str(trace_run.id),
        "realtime_session_id": str(trace_run.realtime_session_id) if trace_run.realtime_session_id else None,
        "realtime_trace_session_id": str(realtime_trace.id) if realtime_trace else None,
        "trace_status": realtime_trace.trace_status if realtime_trace else None,
        "event_type_counts": event_type_counts,
        "permission_audit_count": len(permission_audits),
        "memory_gate_count": len(memory_gate_traces),
        "replay_segment_count": len(replay_segments),
        "redaction_count": len(redactions),
        "raw_media_included": False,
    }
    return {
        "summary": summary,
        "realtime_trace_session": _realtime_trace_session_dict(realtime_trace) if realtime_trace else None,
        "events": [_realtime_trace_event_dict(item) for item in events],
        "participant_event_traces": [_participant_event_trace_dict(item) for item in participant_event_traces],
        "speaker_traces": [_speaker_trace_dict(item) for item in speaker_traces],
        "permission_audits": [_permission_audit_dict(item) for item in permission_audits],
        "memory_gate_traces": [_memory_gate_trace_dict(item) for item in memory_gate_traces],
        "replay": _realtime_replay_dict(replay) if replay else None,
        "replay_segments": [_realtime_replay_segment_dict(item) for item in replay_segments],
        "redactions": [_redaction_event_dict(item) for item in redactions],
        "hard_stop_audits": [_hard_stop_audit_dict(item) for item in hard_stop_audits],
        "trace_steps": [
            {
                "step_name": step.step_name,
                "status": step.status,
                "realtime_copresence_json": step.realtime_copresence_json or {},
                "participant_permission_json": step.participant_permission_json or {},
                "realtime_memory_gate_json": step.realtime_memory_gate_json or {},
            }
            for step in steps
        ],
    }


def _realtime_trace_session_dict(row: RealtimeTraceSession) -> dict:
    return {
        "id": str(row.id),
        "user_id": str(row.user_id),
        "realtime_session_id": str(row.realtime_session_id),
        "co_presence_session_id": str(row.co_presence_session_id) if row.co_presence_session_id else None,
        "trace_run_id": str(row.trace_run_id) if row.trace_run_id else None,
        "trace_status": row.trace_status,
        "trace_level": row.trace_level,
        "raw_capture_policy": row.raw_capture_policy,
        "raw_audio_storage_allowed": row.raw_audio_storage_allowed,
        "raw_screen_storage_allowed": row.raw_screen_storage_allowed,
        "raw_video_storage_allowed": row.raw_video_storage_allowed,
        "redaction_required": row.redaction_required,
        "retention_policy": row.retention_policy,
        "trace_summary": row.trace_summary,
        "policy_snapshot_json": row.policy_snapshot_json or {},
    }


def _realtime_trace_event_dict(row: RealtimeTraceEvent) -> dict:
    return {
        "id": str(row.id),
        "realtime_trace_session_id": str(row.realtime_trace_session_id),
        "realtime_session_id": str(row.realtime_session_id),
        "event_type": row.event_type,
        "event_status": row.event_status,
        "source_participant_id": str(row.source_participant_id) if row.source_participant_id else None,
        "source_channel_id": str(row.source_channel_id) if row.source_channel_id else None,
        "event_summary": row.event_summary,
        "raw_payload_ref": row.raw_payload_ref,
        "raw_payload_storage_allowed": row.raw_payload_storage_allowed,
        "raw_payload_retention_policy": row.raw_payload_retention_policy,
        "event_payload_json": row.event_payload_json or {},
        "occurred_at": row.occurred_at.isoformat() if row.occurred_at else None,
    }


def _participant_event_trace_dict(row: ParticipantEventTrace) -> dict:
    return {
        "id": str(row.id),
        "realtime_trace_event_id": str(row.realtime_trace_event_id),
        "participant_id": str(row.participant_id),
        "permission_action": row.permission_action,
        "permission_allowed": row.permission_allowed,
        "review_required": row.review_required,
        "permission_snapshot_json": row.permission_snapshot_json or {},
    }


def _speaker_trace_dict(row: SpeakerTrace) -> dict:
    return {
        "id": str(row.id),
        "realtime_trace_event_id": str(row.realtime_trace_event_id),
        "voice_session_id": str(row.voice_session_id) if row.voice_session_id else None,
        "voice_turn_id": str(row.voice_turn_id) if row.voice_turn_id else None,
        "speaker_participant_id": str(row.speaker_participant_id) if row.speaker_participant_id else None,
        "speaker_companion_id": str(row.speaker_companion_id) if row.speaker_companion_id else None,
        "speaker_trace_status": row.speaker_trace_status,
        "transcript_retention_policy": row.transcript_retention_policy,
        "transcript_excerpt_ephemeral": row.transcript_excerpt_ephemeral,
        "speaker_payload_json": row.speaker_payload_json or {},
    }


def _permission_audit_dict(row: PermissionAuditEvent) -> dict:
    return {
        "id": str(row.id),
        "realtime_trace_session_id": str(row.realtime_trace_session_id),
        "realtime_trace_event_id": str(row.realtime_trace_event_id) if row.realtime_trace_event_id else None,
        "participant_id": str(row.participant_id) if row.participant_id else None,
        "context_event_id": str(row.context_event_id) if row.context_event_id else None,
        "hard_stop_event_id": str(row.hard_stop_event_id) if row.hard_stop_event_id else None,
        "audit_scope": row.audit_scope,
        "audit_decision": row.audit_decision,
        "requires_redaction_review": row.requires_redaction_review,
        "audit_summary": row.audit_summary,
        "audit_payload_json": row.audit_payload_json or {},
    }


def _memory_gate_trace_dict(row: MemoryGateTrace) -> dict:
    return {
        "id": str(row.id),
        "realtime_trace_session_id": str(row.realtime_trace_session_id),
        "realtime_trace_event_id": str(row.realtime_trace_event_id) if row.realtime_trace_event_id else None,
        "memory_buffer_id": str(row.memory_buffer_id) if row.memory_buffer_id else None,
        "memory_candidate_id": str(row.memory_candidate_id) if row.memory_candidate_id else None,
        "shared_memory_candidate_id": str(row.shared_memory_candidate_id) if row.shared_memory_candidate_id else None,
        "gate_status": row.gate_status,
        "auto_write_blocked": row.auto_write_blocked,
        "gate_summary": row.gate_summary,
        "gate_payload_json": row.gate_payload_json or {},
    }


def _realtime_replay_dict(row: RealtimeReplay) -> dict:
    return {
        "id": str(row.id),
        "realtime_trace_session_id": str(row.realtime_trace_session_id),
        "realtime_session_id": str(row.realtime_session_id),
        "replay_status": row.replay_status,
        "replay_scope": row.replay_scope,
        "includes_transcript_summary": row.includes_transcript_summary,
        "includes_key_events": row.includes_key_events,
        "includes_raw_audio": row.includes_raw_audio,
        "includes_raw_screen": row.includes_raw_screen,
        "includes_raw_video": row.includes_raw_video,
        "redaction_required": row.redaction_required,
        "replay_summary": row.replay_summary,
        "replay_payload_json": row.replay_payload_json or {},
    }


def _realtime_replay_segment_dict(row: RealtimeReplaySegment) -> dict:
    return {
        "id": str(row.id),
        "realtime_replay_id": str(row.realtime_replay_id),
        "source_trace_event_id": str(row.source_trace_event_id) if row.source_trace_event_id else None,
        "segment_type": row.segment_type,
        "segment_order": row.segment_order,
        "segment_status": row.segment_status,
        "segment_summary": row.segment_summary,
        "raw_segment_ref": row.raw_segment_ref,
        "raw_segment_storage_allowed": row.raw_segment_storage_allowed,
        "redaction_required": row.redaction_required,
        "segment_payload_json": row.segment_payload_json or {},
    }


def _redaction_event_dict(row: RedactionEvent) -> dict:
    return {
        "id": str(row.id),
        "realtime_trace_event_id": str(row.realtime_trace_event_id) if row.realtime_trace_event_id else None,
        "realtime_replay_segment_id": str(row.realtime_replay_segment_id) if row.realtime_replay_segment_id else None,
        "context_event_id": str(row.context_event_id) if row.context_event_id else None,
        "redaction_status": row.redaction_status,
        "redaction_policy": row.redaction_policy,
        "audit_required": row.audit_required,
        "redaction_summary": row.redaction_summary,
        "redaction_payload_json": row.redaction_payload_json or {},
    }


def _hard_stop_audit_dict(row: HardStopAuditEvent) -> dict:
    return {
        "id": str(row.id),
        "hard_stop_event_id": str(row.hard_stop_event_id),
        "audit_event_type": row.audit_event_type,
        "audit_status": row.audit_status,
        "affected_scope": row.affected_scope,
        "audit_summary": row.audit_summary,
        "audit_payload_json": row.audit_payload_json or {},
    }


def _step_by_name(steps: list[TraceStep], step_name: str) -> TraceStep | None:
    for step in steps:
        if step.step_name == step_name:
            return step
    return None


def _section(
    step: TraceStep | None,
    *,
    summary: str,
    data_keys: tuple[str, ...],
) -> CompanionTraceSection:
    if step is None:
        return CompanionTraceSection(summary=summary)
    output = step.output_json or {}
    data = {key: output.get(key) for key in data_keys if key in output}
    return CompanionTraceSection(
        step_name=step.step_name,
        status=step.status,
        decision=step.decision,
        summary=summary,
        data=data,
    )


def _delegated_execution_trace_section(s: Session, step: TraceStep | None) -> CompanionTraceSection:
    if step is None:
        return CompanionTraceSection(summary="No delegated execution planning was triggered.")
    output = step.output_json or {}
    delegated_trace_run_id = output.get("delegation_trace_run_id")
    delegated_trace = None
    if delegated_trace_run_id:
        delegated_trace_run = s.get(TraceRun, uuid.UUID(delegated_trace_run_id))
        if delegated_trace_run is not None:
            delegated_steps = list(
                s.execute(
                    select(TraceStep)
                    .where(TraceStep.trace_run_id == delegated_trace_run.id)
                    .order_by(TraceStep.step_order.asc())
                ).scalars().all()
            )
            delegated_trace = {
                "trace_run_id": str(delegated_trace_run.id),
                "status": delegated_trace_run.status,
                "metadata": delegated_trace_run.metadata_ or {},
                "steps": [_ts_dict(item) for item in delegated_steps],
            }
    return CompanionTraceSection(
        step_name=step.step_name,
        status=step.status,
        decision=step.decision,
        summary="Explained delegated execution intent, executor choice, and boundary check.",
        data={
            "delegation_trace_run_id": delegated_trace_run_id,
            "executor_type": output.get("executor_type"),
            "boundary_check": output.get("boundary_check") or {},
            "delegated_trace": delegated_trace,
        },
    )


def _provider_trace_section(trace_run: TraceRun, step: TraceStep | None) -> CompanionTraceSection:
    provider_json = step.provider_json if step and step.provider_json else {}
    data = {
        "model_provider": trace_run.model_provider,
        "model_name": trace_run.model_name,
        "provider_mode": provider_json.get("provider_mode", trace_run.model_provider or "unrecorded"),
        "provider_name": provider_json.get("provider_name"),
        "llm_call_record_ids": _string_ids(trace_run.llm_call_record_ids),
    }
    return CompanionTraceSection(
        step_name=step.step_name if step else None,
        status=step.status if step else None,
        decision=step.decision if step else None,
        summary="Explained provider/model selection and preserved V3 LLM trace references.",
        data=data,
    )


def _tool_file_evidence_trace_section(trace_run: TraceRun, steps: list[TraceStep]) -> CompanionTraceSection:
    return CompanionTraceSection(
        summary="Explained Agent execution tool, file, reranker, evidence, evaluation, and prompt-side signals.",
        data={
            "tool_run_ids": _string_ids(trace_run.tool_run_ids),
            "file_context_usage_ids": _string_ids(trace_run.file_context_usage_ids),
            "evidence_sufficiency_event_ids": _string_ids(trace_run.evidence_sufficiency_event_ids),
            "memory_reranker_run_ids": _string_ids(trace_run.memory_reranker_run_ids),
            "presence_policy_run_ids": _string_ids(trace_run.presence_policy_run_ids),
            "bad_case_signal_ids": _string_ids(trace_run.bad_case_signal_ids),
            "evaluation_signal_ids": _string_ids(trace_run.evaluation_signal_ids),
            "step_sections": [
                {
                    "step_name": step.step_name,
                    "tool": step.tool_json or {},
                    "file_context": step.file_context_json or {},
                    "evidence": step.evidence_json or {},
                    "provider": step.provider_json or {},
                }
                for step in steps
            ],
        },
    )


def _narrative_summary(
    *,
    trace_run: TraceRun,
    companion_context: dict[str, Any],
    companion_identity_step: TraceStep | None,
    co_presence_step: TraceStep | None,
    shared_scene_step: TraceStep | None,
    cross_pending: int,
) -> str:
    companion_name = None
    if companion_identity_step and isinstance(companion_identity_step.output_json, dict):
        companion_name = companion_identity_step.output_json.get("companion_name")
    participant_count = None
    if co_presence_step and isinstance(co_presence_step.output_json, dict):
        participant_count = co_presence_step.output_json.get("participant_count")
    scene_id = None
    if shared_scene_step and isinstance(shared_scene_step.output_json, dict):
        scene_id = shared_scene_step.output_json.get("shared_scene_id")

    parts = [f"Trace {trace_run.id}"]
    if companion_name:
        parts.append(f"activated {companion_name}")
    if participant_count:
        parts.append(f"within a {participant_count}-participant co-presence session")
    if scene_id:
        parts.append("with shared scene context")
    if companion_context.get("shared_memory_candidate_count"):
        parts.append(f"and produced {companion_context['shared_memory_candidate_count']} shared-memory candidate(s)")
    if cross_pending:
        parts.append(f"while surfacing {cross_pending} pending cross-companion review(s)")
    if companion_context.get("delegation_intent_id"):
        parts.append("plus a delegated execution intent")
    return " ".join(parts) + "."


def _consistency_score(persona_guard_status: str | None) -> float | None:
    if persona_guard_status == "passed":
        return 0.9
    if persona_guard_status == "review_required":
        return 0.5
    if persona_guard_status == "blocked":
        return 0.1
    return None


def _string_ids(values: list | None) -> list[str]:
    return [str(value) for value in (values or [])]
