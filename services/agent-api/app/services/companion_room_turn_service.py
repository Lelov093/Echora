"""Companion Room turn durable, transport-neutral multi-Companion Room turn coordinator."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_, select, text

from app.agents.runner import execute_agent_turn
from app.db.models import (
    BadCase,
    BoundarySetting,
    Companion,
    CompanionRoomTurn,
    CompanionRoomTurnStep,
    Conversation,
    CoPresenceParticipant,
    CoPresenceSession,
    FocusModeEvent,
    Message,
    QuietHourSetting,
    ScopedHardStopEvent,
    TraceRun,
)
from app.services import conversation_application_service
from app.services.conversation_service import get_session


TURN_CONTRACT_VERSION = "room-turn.v1"
MAX_SPEAKERS = 3
STEP_LEASE_SECONDS = 90
TERMINAL_TURN_STATUSES = {"completed", "suppressed", "failed", "cancelled"}
TERMINAL_STEP_STATUSES = {"completed", "suppressed", "cancelled"}
_SILENCE_PATTERNS = (
    "不用回复", "先别回复", "不要回复", "保持安静", "安静一下", "只需要听", "先听我说",
)


class CompanionRoomTurnError(RuntimeError):
    def __init__(self, code: str, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


def execute_room_turn(room_id: uuid.UUID, payload: dict[str, Any]) -> dict[str, Any]:
    content = _validated_content(payload.get("content"))
    requested_ids = [_uuid(value) for value in payload.get("target_companion_ids") or []]
    key = _idempotency_key(payload.get("idempotency_key"))
    source = str(payload.get("source") or "web")
    if source not in {"web", "discord_channel"}:
        raise CompanionRoomTurnError("ROOM_TURN_SOURCE_INVALID", "不支持的聊天室消息来源。")
    require_explicit_targets = bool(payload.get("require_explicit_targets", False))
    source_metadata = payload.get("source_metadata") if isinstance(payload.get("source_metadata"), dict) else {}
    turn_id, replay = _claim_room_turn(
        room_id, content, requested_ids, key,
        source=source,
        require_explicit_targets=require_explicit_targets,
        source_metadata=source_metadata,
    )
    if replay:
        replay["idempotent_replay"] = True
        return replay
    return _run_turn(turn_id)


def get_room_turn(room_id: uuid.UUID, turn_id: uuid.UUID) -> dict[str, Any]:
    with get_session() as s:
        turn = s.get(CompanionRoomTurn, turn_id)
        if turn is None or turn.co_presence_session_id != room_id:
            raise CompanionRoomTurnError("ROOM_TURN_NOT_FOUND", "未找到对应的聊天室回合。")
        return _project_turn(s, turn)


def list_room_messages(room_id: uuid.UUID, *, limit: int = 100) -> dict[str, Any]:
    with get_session() as s:
        room, conversation = _room_and_conversation(s, room_id)
        rows = list(s.execute(
            select(Message, Companion.name)
            .join(Companion, Companion.id == Message.companion_id)
            .where(Message.conversation_id == conversation.id, Message.deleted_at.is_(None))
            .order_by(Message.created_at.desc())
            .limit(limit)
        ).all())
        items = [_message_projection(message, name) for message, name in reversed(rows)]
        return {"items": items, "total": len(items), "room_id": str(room.id), "conversation_id": str(conversation.id)}


def cancel_room_turn(room_id: uuid.UUID, turn_id: uuid.UUID) -> dict[str, Any]:
    now = _now()
    with get_session() as s:
        turn = s.execute(select(CompanionRoomTurn).where(
            CompanionRoomTurn.id == turn_id,
            CompanionRoomTurn.co_presence_session_id == room_id,
        ).with_for_update()).scalar_one_or_none()
        if turn is None:
            raise CompanionRoomTurnError("ROOM_TURN_NOT_FOUND", "未找到对应的聊天室回合。")
        if turn.status in TERMINAL_TURN_STATUSES:
            return _project_turn(s, turn)
        turn.cancellation_requested = True
        turn.revision += 1
        for step in _steps(s, turn.id):
            expired_running = step.status == "running" and (
                step.lease_expires_at is None or step.lease_expires_at <= now
            )
            existing_assistant = _existing_step_assistant(s, step) if expired_running else None
            if existing_assistant:
                _mark_step_completed_from_existing(step, existing_assistant, "cancel_reconciliation")
            elif step.status == "planned" or expired_running:
                step.status = "cancelled"
                step.completed_at = now
                step.lease_owner = None
                step.lease_expires_at = None
                step.evidence_json = {**(step.evidence_json or {}), "cancelled_before_execution": True}
        if not any(step.status == "running" for step in _steps(s, turn.id)):
            turn.status = "cancelled"
            turn.completed_at = now
        s.commit()
        return _project_turn(s, turn)


def retry_room_turn_step(room_id: uuid.UUID, turn_id: uuid.UUID, step_id: uuid.UUID) -> dict[str, Any]:
    reconciled = False
    with get_session() as s:
        turn = s.execute(select(CompanionRoomTurn).where(
            CompanionRoomTurn.id == turn_id,
            CompanionRoomTurn.co_presence_session_id == room_id,
        ).with_for_update()).scalar_one_or_none()
        step = s.execute(select(CompanionRoomTurnStep).where(
            CompanionRoomTurnStep.id == step_id,
            CompanionRoomTurnStep.room_turn_id == turn_id,
        ).with_for_update()).scalar_one_or_none()
        if turn is None or step is None:
            raise CompanionRoomTurnError("ROOM_TURN_STEP_NOT_FOUND", "未找到可恢复的伙伴执行步骤。")
        if step.status == "running" and (step.lease_expires_at is None or step.lease_expires_at <= _now()):
            existing_assistant = _existing_step_assistant(s, step)
            if existing_assistant:
                _mark_step_completed_from_existing(step, existing_assistant, "lease_reconciliation")
                turn.status = "running"
                turn.completed_at = None
                turn.revision += 1
                reconciled = True
            else:
                _mark_step_failed(step, {
                    "code": "ROOM_STEP_LEASE_EXPIRED",
                    "message": "上一次伙伴执行已中断，可以安全重试。",
                })
                step.retry_available_at = None
        if not reconciled and step.status != "failed":
            raise CompanionRoomTurnError("ROOM_TURN_STEP_NOT_RETRYABLE", "只有失败的伙伴步骤可以重试。")
        if not reconciled and step.attempt_count >= 3:
            raise CompanionRoomTurnError("ROOM_TURN_STEP_RETRY_EXHAUSTED", "该伙伴步骤已达到重试上限。")
        if not reconciled and step.retry_available_at and step.retry_available_at > _now():
            raise CompanionRoomTurnError(
                "ROOM_TURN_STEP_RETRY_NOT_READY", "该伙伴步骤尚未到达下一次重试时间。",
                {"retry_available_at": step.retry_available_at.isoformat()},
            )
        if not reconciled:
            step.status = "planned"
            step.error_json = {}
            step.retry_available_at = None
            step.completed_at = None
            turn.status = "running"
            turn.completed_at = None
            turn.revision += 1
        s.commit()
    return _run_turn(turn_id)


def _claim_room_turn(
    room_id: uuid.UUID,
    content: str,
    requested_ids: list[uuid.UUID],
    key: str,
    *,
    source: str = "web",
    require_explicit_targets: bool = False,
    source_metadata: dict[str, Any] | None = None,
) -> tuple[uuid.UUID, dict[str, Any] | None]:
    request_hash = hashlib.sha256(
        json.dumps({
            "room_id": str(room_id), "content": content,
            "targets": sorted(map(str, requested_ids)), "source": source,
            "require_explicit_targets": require_explicit_targets,
        }, sort_keys=True).encode()
    ).hexdigest()
    lock_id = int.from_bytes(hashlib.sha256(f"room-turn:{room_id}:{key}".encode()).digest()[:8], "big", signed=True)
    now = _now()
    with get_session() as s:
        s.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
        room, conversation = _room_and_conversation(s, room_id, lock=True)
        existing = s.execute(select(CompanionRoomTurn).where(
            CompanionRoomTurn.co_presence_session_id == room.id,
            CompanionRoomTurn.idempotency_key == key,
        )).scalar_one_or_none()
        if existing:
            if existing.request_hash != request_hash:
                raise CompanionRoomTurnError("ROOM_TURN_IDEMPOTENCY_CONFLICT", "该幂等键已用于不同的聊天室消息。")
            return existing.id, _project_turn(s, existing)

        plan = _build_speaker_plan(
            s, room, content, requested_ids,
            require_explicit_targets=require_explicit_targets,
        )
        user_message = Message(
            user_id=room.user_id,
            companion_id=conversation.companion_id,
            conversation_id=conversation.id,
            role="user",
            content=content,
            metadata_={
                "room_turn_idempotency_key": key,
                "created_by": "companion_room_turn_service",
                "source": source,
                **(source_metadata or {}),
            },
        )
        s.add(user_message)
        s.flush()
        turn = CompanionRoomTurn(
            user_id=room.user_id,
            co_presence_session_id=room.id,
            conversation_id=conversation.id,
            user_message_id=user_message.id,
            idempotency_key=key,
            request_hash=request_hash,
            source=source,
            status="planning",
            speaker_plan_json=plan,
            started_at=now,
            metadata_={
                "contract_version": TURN_CONTRACT_VERSION,
                "raw_cross_companion_payload_shared": False,
                **(source_metadata or {}),
            },
        )
        s.add(turn)
        s.flush()
        user_message.metadata_ = {**user_message.metadata_, "room_turn_id": str(turn.id)}
        for ordinal, item in enumerate(plan["selected"], 1):
            s.add(CompanionRoomTurnStep(
                room_turn_id=turn.id,
                user_id=room.user_id,
                companion_id=_uuid(item["companion_id"]),
                participant_id=_uuid(item["participant_id"]),
                ordinal=ordinal,
                status="suppressed" if item.get("veto_reason") else "planned",
                selection_reason=item["selection_reason"],
                evidence_json={
                    "speaker_plan_version": plan["version"],
                    "veto_reason": item.get("veto_reason"),
                    "observer_auto_promoted": False,
                    "private_memory_shared": False,
                },
                completed_at=now if item.get("veto_reason") else None,
                metadata_={"contract_version": TURN_CONTRACT_VERSION},
            ))
        if not plan["selected"]:
            turn.status = "suppressed"
            turn.completed_at = now
        s.commit()
        return turn.id, None


def _run_turn(turn_id: uuid.UUID) -> dict[str, Any]:
    with get_session() as s:
        turn = s.execute(select(CompanionRoomTurn).where(CompanionRoomTurn.id == turn_id).with_for_update()).scalar_one()
        if turn.status in TERMINAL_TURN_STATUSES:
            return _project_turn(s, turn)
        turn.status = "running"
        turn.revision += 1
        step_ids = [step.id for step in _steps(s, turn.id) if step.status == "planned"]
        s.commit()
    for step_id in step_ids:
        with get_session() as s:
            current = s.get(CompanionRoomTurn, turn_id)
            if current is None or current.cancellation_requested:
                break
        _execute_step(turn_id, step_id)
    _finalize_turn(turn_id)
    with get_session() as s:
        turn = s.get(CompanionRoomTurn, turn_id)
        return _project_turn(s, turn)


def _execute_step(turn_id: uuid.UUID, step_id: uuid.UUID) -> None:
    now = _now()
    lease_owner = f"room-sync:{uuid.uuid4()}"
    with get_session() as s:
        turn = s.get(CompanionRoomTurn, turn_id)
        step = s.execute(select(CompanionRoomTurnStep).where(CompanionRoomTurnStep.id == step_id).with_for_update()).scalar_one()
        if turn is None or step.status in TERMINAL_STEP_STATUSES or turn.cancellation_requested:
            return
        veto = _runtime_veto(s, turn, step)
        if veto:
            step.status = "suppressed"
            step.completed_at = now
            step.evidence_json = {**(step.evidence_json or {}), "runtime_veto": veto}
            s.commit()
            return
        message = s.get(Message, turn.user_message_id)
        companion = s.get(Companion, step.companion_id)
        trace = TraceRun(
            user_id=turn.user_id,
            companion_id=step.companion_id,
            conversation_id=turn.conversation_id,
            message_id=turn.user_message_id,
            agent_graph_name="room_conversation_graph",
            status="started",
            input_summary=(message.content if message else "")[:200],
            metadata_={
                "room_turn_id": str(turn.id), "room_turn_step_id": str(step.id),
                "room_turn_contract_version": TURN_CONTRACT_VERSION,
            },
        )
        s.add(trace)
        s.flush()
        step.trace_run_id = trace.id
        step.status = "running"
        step.attempt_count += 1
        step.started_at = now
        step.lease_owner = lease_owner
        step.lease_expires_at = now + timedelta(seconds=STEP_LEASE_SECONDS)
        step.evidence_json = {**(step.evidence_json or {}), "attempt_started_at": now.isoformat()}
        content = message.content
        mode_key = companion.current_mode or "daily"
        execution = {
            "user_id": str(turn.user_id), "companion_id": str(step.companion_id),
            "conversation_id": str(turn.conversation_id), "user_message_id": str(turn.user_message_id),
            "turn_id": str(turn.id), "step_id": str(step.id), "trace_id": str(trace.id),
            "attempt_count": step.attempt_count,
        }
        s.commit()

    try:
        state = execute_agent_turn(
            user_id=execution["user_id"], companion_id=execution["companion_id"],
            conversation_id=execution["conversation_id"], content=content, mode_key=mode_key,
            user_message_id=execution["user_message_id"], trace_run_id=execution["trace_id"],
            turn_idempotency_key=f"room:{execution['turn_id']}:{execution['step_id']}:{execution['attempt_count']}",
            room_turn_id=execution["turn_id"], room_turn_step_id=execution["step_id"],
        )
        result = conversation_application_service.project_conversation_turn(state, content)
        conversation_application_service._store_turn_response(_uuid(execution["trace_id"]), result)
        assistant = result.get("assistant_message") or {}
        provider_error = next((item for item in state.get("errors", []) if item.get("step") == "response_generation"), None)
        with get_session() as s:
            persisted = s.execute(select(CompanionRoomTurnStep).where(CompanionRoomTurnStep.id == step_id).with_for_update()).scalar_one()
            if persisted.status == "completed":
                return
            if assistant.get("id") and not provider_error:
                persisted.status = "completed"
                persisted.assistant_message_id = _uuid(assistant["id"])
                persisted.completed_at = _now()
                persisted.error_json = {}
                persisted.lease_owner = None
                persisted.lease_expires_at = None
                persisted.evidence_json = {
                    **(persisted.evidence_json or {}),
                    "provider_mode": result.get("provider_mode"),
                    "provider_name": result.get("provider_name"),
                    "context_snapshot_contract": ((state.get("companion_context_snapshot") or {}).get("contract_version")),
                    "post_turn_effects_status": (result.get("post_turn_effects") or {}).get("status"),
                    "trace_status": (result.get("trace") or {}).get("status"),
                }
            else:
                _mark_step_failed(persisted, provider_error or {"code": "ROOM_STEP_NO_RESPONSE", "message": "伙伴未生成可持久化回复。"})
            s.commit()
    except Exception as exc:
        with get_session() as s:
            persisted = s.execute(select(CompanionRoomTurnStep).where(CompanionRoomTurnStep.id == step_id).with_for_update()).scalar_one()
            current_turn = s.get(CompanionRoomTurn, turn_id)
            if persisted.status != "completed":
                existing_assistant = _existing_step_assistant(s, persisted)
                if existing_assistant:
                    _mark_step_completed_from_existing(persisted, existing_assistant, "exception_reconciliation")
                else:
                    _mark_step_failed(persisted, {
                        "code": getattr(exc, "code", "ROOM_STEP_RUNTIME_FAILED"),
                        "message": getattr(exc, "message", "伙伴执行暂时失败。"),
                        "failure_type": type(exc).__name__,
                    })
            trace_row = s.get(TraceRun, persisted.trace_run_id) if persisted.trace_run_id else None
            if trace_row and trace_row.status != "completed":
                trace_row.status = "failed"
            if persisted.status == "failed":
                _safe_append_bad_case(s, current_turn, persisted)
            s.commit()


def _finalize_turn(turn_id: uuid.UUID) -> None:
    now = _now()
    with get_session() as s:
        turn = s.execute(select(CompanionRoomTurn).where(CompanionRoomTurn.id == turn_id).with_for_update()).scalar_one()
        steps = _steps(s, turn.id)
        if turn.cancellation_requested:
            for step in steps:
                if step.status == "planned":
                    step.status = "cancelled"; step.completed_at = now
        completed = sum(step.status == "completed" for step in steps)
        failed = sum(step.status == "failed" for step in steps)
        suppressed = sum(step.status == "suppressed" for step in steps)
        cancelled = sum(step.status == "cancelled" for step in steps)
        pending = sum(step.status in {"planned", "running"} for step in steps)
        if pending:
            turn.status = "running"
            turn.completed_at = None
            turn.result_json = {
                "completed_steps": completed, "failed_steps": failed,
                "suppressed_steps": suppressed, "cancelled_steps": cancelled,
                "pending_steps": pending,
            }
            s.commit()
            return
        if completed and not failed:
            status = "completed"
        elif completed and failed:
            status = "partial_failed"
        elif failed:
            status = "failed"
        elif turn.cancellation_requested or cancelled:
            status = "cancelled"
        else:
            status = "suppressed"
        turn.status = status
        turn.completed_at = now
        turn.revision += 1
        turn.result_json = {
            "completed_steps": completed, "failed_steps": failed,
            "suppressed_steps": suppressed, "cancelled_steps": cancelled,
        }
        s.commit()


def _build_speaker_plan(
    s,
    room: CoPresenceSession,
    content: str,
    requested_ids: list[uuid.UUID],
    *,
    require_explicit_targets: bool = False,
) -> dict[str, Any]:
    participants = list(s.execute(select(CoPresenceParticipant).where(
        CoPresenceParticipant.co_presence_session_id == room.id,
        CoPresenceParticipant.participant_type == "companion",
    ).order_by(CoPresenceParticipant.joined_at.asc(), CoPresenceParticipant.created_at.asc())).scalars().all())
    active_speakers = [item for item in participants if item.join_status == "active" and item.can_speak and item.participant_role != "observing_companion"]
    companions = {item.id: item for item in s.execute(select(Companion).where(Companion.id.in_([p.participant_companion_id for p in participants]))).scalars().all()}
    mentioned = [p for p in active_speakers if _mentioned(content, companions.get(p.participant_companion_id))]
    if requested_ids:
        unknown = [str(value) for value in requested_ids if value not in {p.participant_companion_id for p in active_speakers}]
        if unknown:
            raise CompanionRoomTurnError("ROOM_TURN_TARGET_NOT_SPEAKER", "所选伙伴不在当前允许发言列表中。", {"companion_ids": unknown})
        candidates = [p for p in active_speakers if p.participant_companion_id in requested_ids]
        reason = "explicit_selection"
    elif require_explicit_targets:
        candidates = []
        reason = "explicit_target_required"
    elif mentioned:
        candidates = mentioned
        reason = "explicit_mention"
    else:
        candidates = active_speakers
        reason = "active_speaker_roster"
    if len(candidates) > MAX_SPEAKERS:
        candidates = candidates[:MAX_SPEAKERS]
    silence = any(pattern in content for pattern in _SILENCE_PATTERNS)
    selected = []
    for participant in candidates:
        selected.append({
            "participant_id": str(participant.id),
            "companion_id": str(participant.participant_companion_id),
            "companion_name": (companions.get(participant.participant_companion_id).name if companions.get(participant.participant_companion_id) else "Companion"),
            "selection_reason": reason,
            "veto_reason": "meaningful_silence_requested" if silence else None,
        })
    return {
        "version": TURN_CONTRACT_VERSION,
        "strategy": "bounded_explicit_then_active_roster",
        "explicit_targets_required": require_explicit_targets,
        "max_speakers": MAX_SPEAKERS,
        "selected": selected,
        "excluded": [
            {"companion_id": str(p.participant_companion_id), "reason": _participant_exclusion(p)}
            for p in participants if p not in candidates
        ],
        "observer_auto_promotion": False,
        "companion_to_companion_followups": False,
    }


def _runtime_veto(s, turn: CompanionRoomTurn, step: CompanionRoomTurnStep) -> str | None:
    participant = s.get(CoPresenceParticipant, step.participant_id)
    if participant is None or participant.join_status != "active":
        return "participant_inactive"
    if not participant.can_speak or participant.participant_role == "observing_companion":
        return "participant_not_speaker"
    room = s.get(CoPresenceSession, turn.co_presence_session_id)
    if room is None or room.session_status != "active":
        return "room_not_active"
    stop = s.execute(select(ScopedHardStopEvent).where(
        ScopedHardStopEvent.user_id == turn.user_id,
        ScopedHardStopEvent.hard_stop_status == "active",
        ScopedHardStopEvent.released_at.is_(None),
        ScopedHardStopEvent.stops_speaking.is_(True),
        or_(
            ScopedHardStopEvent.hard_stop_scope == "all_realtime",
            (ScopedHardStopEvent.hard_stop_scope == "companion")
            & (ScopedHardStopEvent.companion_id == step.companion_id),
        ),
    ).order_by(ScopedHardStopEvent.created_at.desc()).limit(1)).scalar_one_or_none()
    if stop:
        return "hard_stop_active"
    focus = s.execute(select(FocusModeEvent).where(
        FocusModeEvent.user_id == turn.user_id,
        FocusModeEvent.focus_status.in_(["active", "started"]),
        FocusModeEvent.ended_at.is_(None),
        FocusModeEvent.suppress_presence.is_(True),
        or_(
            FocusModeEvent.focus_scope == "all_realtime",
            (FocusModeEvent.focus_scope == "companion")
            & (FocusModeEvent.companion_id == step.companion_id),
        ),
    ).order_by(FocusModeEvent.created_at.desc()).limit(1)).scalar_one_or_none()
    if focus:
        return "focus_mode_active"
    quiet = s.execute(select(QuietHourSetting).where(
        QuietHourSetting.user_id == turn.user_id,
        QuietHourSetting.quiet_status == "active",
        or_(QuietHourSetting.companion_id.is_(None), QuietHourSetting.companion_id == step.companion_id),
    ).order_by(QuietHourSetting.created_at.desc())).scalars().all()
    if any(_quiet_hour_active(item, _now()) for item in quiet):
        return "quiet_hours_active"
    return None


def _quiet_hour_active(setting: QuietHourSetting, now: datetime) -> bool:
    try:
        local = now.astimezone(ZoneInfo(setting.timezone or "UTC"))
    except ZoneInfoNotFoundError:
        local = now
    if setting.day_of_week is not None and setting.day_of_week != local.weekday():
        return False
    minute = local.hour * 60 + local.minute
    start, end = setting.start_minute, setting.end_minute
    if start == end:
        return True
    return start <= minute < end if start < end else minute >= start or minute < end


def _mark_step_failed(step: CompanionRoomTurnStep, error: dict[str, Any]) -> None:
    if step.status == "completed":
        return
    step.status = "failed"
    step.completed_at = _now()
    step.retry_available_at = _now() + timedelta(seconds=min(60, 5 * (2 ** max(step.attempt_count - 1, 0))))
    step.error_json = {
        "code": str(error.get("code") or "ROOM_STEP_FAILED"),
        "message": str(error.get("message") or "伙伴执行暂时失败。"),
        "failure_type": error.get("failure_type"),
    }
    step.lease_owner = None
    step.lease_expires_at = None


def _append_bad_case(s, turn: CompanionRoomTurn, step: CompanionRoomTurnStep) -> None:
    s.add(BadCase(
        user_id=turn.user_id, companion_id=step.companion_id,
        conversation_id=turn.conversation_id, message_id=turn.user_message_id,
        trace_run_id=step.trace_run_id, type="other",
        title="Room Companion execution failed",
        description="A Companion Room turn Room Turn Step failed and remains retryable.",
        severity="medium", status="open", candidate_for_evaluation=True,
        regression_seed_json={"room_turn_id": str(turn.id), "room_turn_step_id": str(step.id), "error_code": step.error_json.get("code")},
        metadata_={"source": "room_turn"},
    ))


def _safe_append_bad_case(s, turn: CompanionRoomTurn, step: CompanionRoomTurnStep) -> None:
    """Bad-case recording must never replace the original durable step failure."""
    try:
        with s.begin_nested():
            _append_bad_case(s, turn, step)
            s.flush()
    except Exception:
        step.evidence_json = {**(step.evidence_json or {}), "bad_case_recording": "failed"}


def _existing_step_assistant(s, step: CompanionRoomTurnStep) -> Message | None:
    return s.execute(select(Message).where(
        Message.role == "assistant",
        Message.deleted_at.is_(None),
        Message.metadata_["room_turn_step_id"].astext == str(step.id),
    ).order_by(Message.created_at.asc()).limit(1)).scalar_one_or_none()


def _mark_step_completed_from_existing(step: CompanionRoomTurnStep, message: Message, reason: str) -> None:
    step.status = "completed"
    step.assistant_message_id = message.id
    step.completed_at = message.created_at or _now()
    step.error_json = {}
    step.retry_available_at = None
    step.lease_owner = None
    step.lease_expires_at = None
    step.evidence_json = {
        **(step.evidence_json or {}),
        "reconciled_from_persisted_assistant": True,
        "reconciliation_reason": reason,
    }


def _project_turn(s, turn: CompanionRoomTurn) -> dict[str, Any]:
    steps = _steps(s, turn.id)
    companions = {item.id: item.name for item in s.execute(select(Companion).where(Companion.id.in_([step.companion_id for step in steps]))).scalars().all()} if steps else {}
    return {
        "id": str(turn.id), "room_id": str(turn.co_presence_session_id),
        "conversation_id": str(turn.conversation_id), "user_message_id": str(turn.user_message_id),
        "idempotency_key": turn.idempotency_key, "source": turn.source, "status": turn.status,
        "cancellation_requested": turn.cancellation_requested, "speaker_plan": turn.speaker_plan_json or {},
        "result": turn.result_json or {}, "error": turn.error_json or {}, "revision": turn.revision,
        "started_at": _iso(turn.started_at), "completed_at": _iso(turn.completed_at),
        "steps": [{
            "id": str(step.id), "companion_id": str(step.companion_id),
            "companion_name": companions.get(step.companion_id, "Companion"),
            "participant_id": str(step.participant_id), "ordinal": step.ordinal,
            "status": step.status, "selection_reason": step.selection_reason,
            "attempt_count": step.attempt_count, "trace_run_id": str(step.trace_run_id) if step.trace_run_id else None,
            "assistant_message_id": str(step.assistant_message_id) if step.assistant_message_id else None,
            "evidence": step.evidence_json or {}, "error": step.error_json or {},
            "retry_available_at": _iso(step.retry_available_at), "completed_at": _iso(step.completed_at),
            "lease_expires_at": _iso(step.lease_expires_at),
        } for step in steps],
        "idempotent_replay": False,
    }


def _message_projection(message: Message, companion_name: str) -> dict[str, Any]:
    return {
        "id": str(message.id), "role": message.role, "content": message.content,
        "content_format": message.content_format, "companion_id": str(message.companion_id),
        "companion_name": companion_name, "model_provider": message.model_provider,
        "model_name": message.model_name, "metadata": message.metadata_ or {},
        "created_at": _iso(message.created_at),
    }


def _room_and_conversation(s, room_id: uuid.UUID, *, lock: bool = False) -> tuple[CoPresenceSession, Conversation]:
    stmt = select(CoPresenceSession).where(CoPresenceSession.id == room_id)
    if lock:
        stmt = stmt.with_for_update()
    room = s.execute(stmt).scalar_one_or_none()
    if room is None or room.session_source != "companion_home":
        raise CompanionRoomTurnError("COMPANION_ROOM_NOT_FOUND", "聊天室不存在或不可访问。")
    if room.session_status != "active":
        raise CompanionRoomTurnError("COMPANION_ROOM_NOT_ACTIVE", "请先恢复聊天室再继续对话。")
    conversation = s.execute(select(Conversation).where(
        Conversation.co_presence_session_id == room.id,
        Conversation.deleted_at.is_(None),
    ).order_by(Conversation.created_at.asc()).limit(1)).scalar_one_or_none()
    if conversation is None or conversation.status != "active":
        raise CompanionRoomTurnError("ROOM_CONVERSATION_NOT_ACTIVE", "聊天室的持久对话当前不可用。")
    return room, conversation


def _steps(s, turn_id: uuid.UUID) -> list[CompanionRoomTurnStep]:
    return list(s.execute(select(CompanionRoomTurnStep).where(
        CompanionRoomTurnStep.room_turn_id == turn_id,
    ).order_by(CompanionRoomTurnStep.ordinal.asc())).scalars().all())


def _participant_exclusion(participant: CoPresenceParticipant) -> str:
    if participant.join_status != "active": return "inactive_or_revoked"
    if participant.participant_role == "observing_companion": return "observer"
    if not participant.can_speak: return "muted"
    return "not_selected"


def _mentioned(content: str, companion: Companion | None) -> bool:
    if companion is None or not companion.name:
        return False
    return re.search(rf"(?<!\w)@{re.escape(companion.name)}(?:\b|\s|，|。|！|？|:|：|$)", content, re.IGNORECASE) is not None


def _validated_content(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CompanionRoomTurnError("ROOM_TURN_CONTENT_REQUIRED", "请输入要发送到聊天室的内容。")
    content = value.strip()
    if len(content) > 20_000:
        raise CompanionRoomTurnError("ROOM_TURN_CONTENT_TOO_LONG", "聊天室消息不能超过 20000 个字符。")
    return content


def _idempotency_key(value: Any) -> str:
    key = value.strip() if isinstance(value, str) else ""
    if not key:
        return str(uuid.uuid4())
    if len(key) > 200:
        raise CompanionRoomTurnError("ROOM_TURN_IDEMPOTENCY_KEY_INVALID", "幂等键不能超过 200 个字符。")
    return key


def _uuid(value: Any) -> uuid.UUID:
    return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


__all__ = [
    "CompanionRoomTurnError", "execute_room_turn", "get_room_turn",
    "list_room_messages", "cancel_room_turn", "retry_room_turn_step",
]
