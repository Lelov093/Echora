"""bounded Tool durable, Companion-scoped daily Tool Runtime."""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select, text as sql_text
from sqlalchemy.orm import Session

from app.agents.state import ConversationAgentState
from app.db.models import (
    BadCase,
    CompanionRoomTurn,
    CompanionRoomTurnStep,
    Conversation,
    Message,
    ScopedHardStopEvent,
    ToolDefinition,
    ToolPermission,
    ToolRun,
    ToolRunArtifact,
    ToolRunStep,
    ToolResource,
)
from app.services.conversation_service import ConversationTurnError, get_session
from app.tools.adapters import AdapterResult, ToolAdapterError, execute_adapter
from app.tools.capabilities import CAPABILITIES, CONTRACT_VERSION, requires_confirmation
from app.tools.selection import SelectionResult, select_tool


TERMINAL_STATUSES = {"succeeded", "failed", "cancelled", "blocked", "timed_out"}
ACTIVE_STATUSES = {"awaiting_input", "awaiting_confirmation", "queued", "running", "retry_scheduled"}


def execute_task_tool_step(
    session: Session,
    state: ConversationAgentState,
    *,
    capability: str,
    arguments: dict[str, Any],
    task_step_id: uuid.UUID,
    attempt_number: int,
) -> ToolRun:
    """Reuse the authoritative ToolRun path for one scoped TaskStep attempt."""
    if capability not in CAPABILITIES:
        raise ConversationTurnError(
            "TASK_TOOL_CAPABILITY_UNKNOWN",
            "TaskStep requested an unknown typed capability.",
            {"capability": capability},
        )
    context = _scope_context(session, state)
    selection = SelectionResult(
        capability=capability,
        arguments=arguments,
        confidence=1.0,
        rationale="conversation_task_step",
        provider_name="conversation_task_runtime",
        model_name=None,
    )
    run = _create_run(
        session,
        state,
        selection,
        context,
        idempotency_suffix=f"task-step-{task_step_id}-attempt-{attempt_number}",
    )
    run.requested_by = "conversation_task"
    run.metadata_ = {
        **(run.metadata_ or {}),
        "conversation_task_step_id": str(task_step_id),
        "conversation_task_attempt": attempt_number,
    }
    if run.status == "queued":
        _execute_locked(session, run)
    # A TaskRun owns an asynchronous Conversation turn and must return a
    # terminal observation before the Companion composes its reply. Exhaust the
    # already-bounded retry budget inline for low-risk task tools. Each attempt
    # remains durable, and a process failure still leaves retry_scheduled truth
    # for the normal worker to recover.
    while (
        run.status == "retry_scheduled"
        and run.attempt_count < run.max_attempts
        and not run.confirmation_required
        and run.risk_level == "low"
    ):
        session.commit()
        run.status = "queued"
        run.next_attempt_at = None
        _execute_locked(session, run)
    return run


def request_task_tool_cancellation(
    session: Session,
    run: ToolRun,
    *,
    reason: str,
) -> ToolRun:
    """Reuse the authoritative monotonic ToolRun cancellation transition."""
    context = _run_context(
        session,
        run,
        run.companion_id,
        run.conversation_id,
    )
    return _cancel_locked(session, run, context, reason)


def ensure_builtin_definitions() -> int:
    """Idempotently register the nine versioned built-ins; registration is not execution."""
    with get_session() as session:
        session.execute(sql_text("SELECT pg_advisory_xact_lock(:key)"), {"key": 404202})
        for capability in CAPABILITIES:
            _ensure_definition(session, capability)
        session.commit()
    return len(CAPABILITIES)


def process_conversation_tool_turn(state: ConversationAgentState) -> ConversationAgentState:
    """Select, validate and possibly execute one bounded tool within the current turn."""
    with get_session() as session:
        context = _scope_context(session, state)
        pending = session.execute(
            select(ToolRun)
            .where(
                ToolRun.user_id == context["user_id"],
                ToolRun.companion_id == context["companion_id"],
                ToolRun.conversation_id == context["conversation_id"],
                ToolRun.status.in_({"awaiting_input", "awaiting_confirmation"}),
                ToolRun.deleted_at.is_(None),
            )
            .order_by(ToolRun.created_at.desc())
            .with_for_update(skip_locked=True)
        ).scalars().first()
        prior_terminal = session.execute(
            select(ToolRun)
            .where(
                ToolRun.user_id == context["user_id"],
                ToolRun.companion_id == context["companion_id"],
                ToolRun.conversation_id == context["conversation_id"],
                ToolRun.status.in_(TERMINAL_STATUSES),
                ToolRun.deleted_at.is_(None),
            )
            .order_by(ToolRun.created_at.desc())
        ).scalars().first()
        selection = select_tool(
            state.get("user_input", ""),
            pending=_run_projection(pending) if pending else None,
            prior_terminal=_selection_projection(prior_terminal),
            recent_messages=state.get("recent_messages", []),
        )
        if pending and selection.action in {"confirm", "cancel"}:
            run = _confirm_locked(session, pending, context) if selection.action == "confirm" else _cancel_locked(session, pending, context, "user_cancelled_in_conversation")
            if selection.action == "confirm":
                _execute_locked(session, run)
            _apply_run_to_state(state, run, selection)
            session.commit()
            return state
        if pending and pending.status == "awaiting_input":
            run = _complete_pending_input(session, pending, selection, context)
            _apply_run_to_state(state, run, selection)
            session.commit()
            return state
        if selection.capability is None:
            state.setdefault("trace_steps", []).append({"step": "tool_selection", "order": 45, "status": "skipped", "reason": selection.rationale})
            return state

        parent = (
            prior_terminal
            if selection.continues_tool_run
            and prior_terminal
            and prior_terminal.capability == selection.capability
            else None
        )
        run = _create_run(session, state, selection, context, parent_run=parent)
        runs = [run]
        if run.status == "queued":
            _execute_locked(session, run)
            repair = _bounded_repair_child(
                session, state, run, selection, context, step_number=1
            )
            if repair is not None:
                runs.append(repair)
                run = repair
        _apply_run_to_state(
            state,
            run,
            selection,
            runs=runs,
            parent_run=parent,
        )
        session.commit()
        return state


def confirm_tool_run(
    tool_run_id: uuid.UUID,
    *,
    companion_id: uuid.UUID,
    conversation_id: uuid.UUID | None = None,
) -> dict[str, Any] | None:
    projection: dict[str, Any] | None = None
    with get_session() as session:
        run = session.get(ToolRun, tool_run_id, with_for_update=True)
        if run is None:
            return None
        context = _run_context(session, run, companion_id, conversation_id)
        from app.services.conversation_task_runtime_service import (
            ensure_task_tool_confirmation_allowed,
        )

        ensure_task_tool_confirmation_allowed(session, run.id)
        _confirm_locked(session, run, context)
        _execute_locked(session, run)
        session.commit()
        session.refresh(run)
        projection = _run_projection(run)
    _reconcile_conversation_task(tool_run_id)
    return projection


def cancel_tool_run(
    tool_run_id: uuid.UUID,
    *,
    companion_id: uuid.UUID,
    conversation_id: uuid.UUID | None = None,
    reason: str | None = None,
) -> dict[str, Any] | None:
    projection: dict[str, Any] | None = None
    with get_session() as session:
        run = session.get(ToolRun, tool_run_id, with_for_update=True)
        if run is None:
            return None
        context = _run_context(session, run, companion_id, conversation_id)
        _cancel_locked(session, run, context, reason or "user_cancelled")
        session.commit()
        session.refresh(run)
        projection = _run_projection(run)
    _reconcile_conversation_task(tool_run_id)
    return projection


def retry_tool_run(
    tool_run_id: uuid.UUID,
    *,
    companion_id: uuid.UUID,
    conversation_id: uuid.UUID | None = None,
) -> dict[str, Any] | None:
    with get_session() as session:
        original = session.get(ToolRun, tool_run_id, with_for_update=True)
        if original is None:
            return None
        context = _run_context(session, original, companion_id, conversation_id)
        if original.status not in {"failed", "timed_out", "retry_scheduled"}:
            raise ConversationTurnError("TOOL_RUN_NOT_RETRYABLE", "Only failed, timed-out or retry-scheduled ToolRuns can be retried.", {"status": original.status})
        if original.attempt_count >= original.max_attempts:
            raise ConversationTurnError("TOOL_RUN_RETRY_EXHAUSTED", "ToolRun retry limit has been reached.")
        child = ToolRun(
            user_id=original.user_id,
            companion_id=original.companion_id,
            conversation_id=original.conversation_id,
            trace_run_id=original.trace_run_id,
            tool_definition_id=original.tool_definition_id,
            parent_tool_run_id=original.id,
            request_message_id=original.request_message_id,
            requested_by="user_retry",
            capability=original.capability,
            adapter_name=original.adapter_name,
            adapter_version=original.adapter_version,
            status="queued",
            risk_level=original.risk_level,
            permission_required=original.permission_required,
            permission_granted=original.permission_granted,
            confirmation_required=original.confirmation_required,
            confirmation_summary=original.confirmation_summary,
            confirmed_at=original.confirmed_at,
            confirmed_by=original.confirmed_by,
            idempotency_key=f"retry:{original.id}:{original.attempt_count + 1}",
            input_schema_version=original.input_schema_version,
            output_schema_version=original.output_schema_version,
            input_json=original.input_json,
            max_attempts=original.max_attempts,
            timeout_seconds=original.timeout_seconds,
        )
        session.add(child)
        session.flush()
        _execute_locked(session, child)
        session.commit()
        session.refresh(child)
        return _run_projection(child)


def execute_due_retries(*, worker_id: str, limit: int = 10) -> dict[str, int]:
    """Claim and isolate due retry jobs; safe for multiple workers."""
    now = datetime.now(timezone.utc)
    counts = {"claimed": 0, "succeeded": 0, "failed": 0}
    with get_session() as session:
        runs = session.execute(
            select(ToolRun)
            .where(
                ToolRun.status == "retry_scheduled",
                ToolRun.next_attempt_at <= now,
                (ToolRun.lease_expires_at.is_(None)) | (ToolRun.lease_expires_at <= now),
                ToolRun.deleted_at.is_(None),
            )
            .order_by(ToolRun.next_attempt_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).scalars().all()
        for run in runs:
            run.status = "queued"
            run.lease_owner = worker_id
            run.lease_expires_at = now + timedelta(seconds=max(30, run.timeout_seconds + 10))
        counts["claimed"] = len(runs)
        session.commit()
        run_ids = [run.id for run in runs]
    for run_id in run_ids:
        try:
            with get_session() as session:
                run = session.get(ToolRun, run_id, with_for_update=True)
                if run is None or run.status != "queued" or run.lease_owner != worker_id:
                    continue
                _execute_locked(session, run)
                counts["succeeded" if run.status == "succeeded" else "failed"] += 1
                session.commit()
            _reconcile_conversation_task(run_id)
        except Exception as exc:
            counts["failed"] += 1
            # A worker-level failure must not strand a claimed job in queued forever.
            with get_session() as recovery_session:
                run = recovery_session.get(ToolRun, run_id, with_for_update=True)
                if run is not None and run.status == "queued" and run.lease_owner == worker_id:
                    run.status = "retry_scheduled" if run.attempt_count < run.max_attempts else "failed"
                    run.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=30) if run.status == "retry_scheduled" else None
                    run.completed_at = datetime.now(timezone.utc) if run.status == "failed" else None
                    run.error_json = {
                        "code": "TOOL_WORKER_FAILURE",
                        "message": "工具后台执行遇到隔离故障。",
                        "retryable": run.status == "retry_scheduled",
                        "details": {"error_type": type(exc).__name__},
                        "attempt": run.attempt_count,
                    }
                    run.terminal_reason = "worker_retry_scheduled" if run.status == "retry_scheduled" else "worker_failure"
                    run.lease_owner = None
                    run.lease_expires_at = None
                    recovery_session.commit()
    return counts


def deliver_due_reminders(*, limit: int = 20) -> dict[str, int]:
    """Deliver local reminders once, independent of any browser session."""
    now = datetime.now(timezone.utc)
    counts = {"delivered": 0, "failed": 0}
    with get_session() as session:
        reminders = session.execute(
            select(ToolResource)
            .where(
                ToolResource.resource_type == "reminder",
                ToolResource.status == "active",
                ToolResource.due_at <= now,
                ToolResource.deleted_at.is_(None),
            )
            .order_by(ToolResource.due_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).scalars().all()
        for reminder in reminders:
            try:
                conversation = session.get(Conversation, reminder.conversation_id) if reminder.conversation_id else None
                if conversation is None or conversation.status != "active" or conversation.deleted_at is not None:
                    reminder.status = "cancelled"
                    reminder.resource_json = {**(reminder.resource_json or {}), "delivery_error": "conversation_unavailable", "delivery_checked_at": now.isoformat()}
                    counts["failed"] += 1
                    continue
                message = Message(
                    user_id=reminder.user_id,
                    companion_id=reminder.companion_id,
                    conversation_id=conversation.id,
                    role="assistant",
                    content=f"提醒你：{reminder.title}" + (f"\n\n{reminder.content}" if reminder.content else ""),
                    content_format="markdown",
                    model_provider="echora_tool_runtime",
                    model_name="local_reminder_v1",
                    metadata_={"tool_resource_id": str(reminder.id), "resource_type": "reminder", "due_at": reminder.due_at.isoformat() if reminder.due_at else None},
                )
                session.add(message)
                session.flush()
                reminder.status = "completed"
                reminder.completed_at = now
                reminder.resource_json = {**(reminder.resource_json or {}), "delivered_message_id": str(message.id), "delivered_at": now.isoformat()}
                counts["delivered"] += 1
            except Exception as exc:
                reminder.resource_json = {**(reminder.resource_json or {}), "delivery_error": type(exc).__name__, "delivery_checked_at": now.isoformat()}
                counts["failed"] += 1
        session.commit()
    return counts


def list_tool_resources(*, companion_id: uuid.UUID, resource_type: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    with get_session() as session:
        statement = select(ToolResource).where(
            ToolResource.companion_id == companion_id,
            ToolResource.deleted_at.is_(None),
        )
        if resource_type:
            statement = statement.where(ToolResource.resource_type == resource_type)
        if status:
            statement = statement.where(ToolResource.status == status)
        rows = session.execute(statement.order_by(ToolResource.created_at.desc()).limit(100)).scalars().all()
        return [{"id": str(row.id), "companion_id": str(row.companion_id), "conversation_id": str(row.conversation_id) if row.conversation_id else None, "resource_type": row.resource_type, "title": row.title, "content": row.content, "status": row.status, "starts_at": row.starts_at.isoformat() if row.starts_at else None, "due_at": row.due_at.isoformat() if row.due_at else None, "timezone": row.timezone_name, "resource_json": row.resource_json or {}, "created_at": row.created_at.isoformat() if row.created_at else None} for row in rows]


def _scope_context(session: Session, state: ConversationAgentState) -> dict[str, uuid.UUID]:
    user_id = uuid.UUID(state["user_id"])
    companion_id = uuid.UUID(state["companion_id"])
    conversation_id = uuid.UUID(state["conversation_id"])
    conversation = session.get(Conversation, conversation_id)
    room_scope_valid = _room_tool_scope_valid(session, conversation, companion_id, state)
    if conversation is None or conversation.user_id != user_id or (conversation.companion_id != companion_id and not room_scope_valid) or conversation.status != "active" or conversation.deleted_at is not None:
        raise ConversationTurnError("TOOL_SCOPE_MISMATCH", "Tool turn scope does not match the active Conversation.")
    return {"user_id": user_id, "companion_id": companion_id, "conversation_id": conversation_id}


def _run_context(session: Session, run: ToolRun, companion_id: uuid.UUID, conversation_id: uuid.UUID | None) -> dict[str, uuid.UUID]:
    if run.companion_id != companion_id or (conversation_id and run.conversation_id != conversation_id):
        raise ConversationTurnError("TOOL_SCOPE_MISMATCH", "ToolRun does not belong to the requested Companion/Conversation.")
    conversation = session.get(Conversation, run.conversation_id) if run.conversation_id else None
    room_scope_valid = _room_tool_run_scope_valid(session, conversation, run)
    if conversation is not None and ((conversation.companion_id != run.companion_id and not room_scope_valid) or conversation.user_id != run.user_id):
        raise ConversationTurnError("TOOL_SCOPE_MISMATCH", "ToolRun owner and Conversation scope do not match.")
    return {"user_id": run.user_id, "companion_id": run.companion_id, "conversation_id": run.conversation_id}


def _create_run(
    session: Session,
    state: ConversationAgentState,
    selection: SelectionResult,
    context: dict[str, uuid.UUID],
    *,
    parent_run: ToolRun | None = None,
    idempotency_suffix: str | None = None,
) -> ToolRun:
    spec = CAPABILITIES[selection.capability]
    definition = _ensure_definition(session, selection.capability)
    _check_hard_stop(session, context)
    permission = _resolve_permission(session, definition, context)
    if permission and (
        permission.policy in {"disabled", "deny"}
        or permission.status in {"denied", "revoked", "expired"}
    ):
        status = "blocked"
        terminal_reason = "tool_permission_denied"
    else:
        status = "planned"
        terminal_reason = None
    effective_arguments = {
        **((parent_run.input_json or {}) if parent_run else {}),
        **selection.arguments,
    }
    validated, missing, validation_error = _validate_payload(
        selection.capability, effective_arguments, selection.missing_fields
    )
    safety_confirmation = requires_confirmation(
        selection.capability, validated or effective_arguments
    )
    permission_scope = dict(permission.scope_json or {}) if permission else {}
    policy_confirmation = bool(
        permission
        and (
            permission.policy == "ask_every_time"
            or (
                permission.policy == "ask_once"
                and not permission_scope.get("ask_once_granted_at")
            )
        )
    )
    confirmation = safety_confirmation or policy_confirmation
    if status != "blocked":
        status = "awaiting_input" if missing else ("awaiting_confirmation" if confirmation else "queued")
    idempotency_key = (
        f"{state.get('turn_idempotency_key') or state.get('trace_run_id')}:"
        f"{selection.capability}{':' + idempotency_suffix if idempotency_suffix else ''}"
    )
    existing = session.execute(
        select(ToolRun).where(
            ToolRun.user_id == context["user_id"],
            ToolRun.companion_id == context["companion_id"],
            ToolRun.conversation_id == context["conversation_id"],
            ToolRun.idempotency_key == idempotency_key,
            ToolRun.deleted_at.is_(None),
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    run = ToolRun(
        user_id=context["user_id"], companion_id=context["companion_id"], conversation_id=context["conversation_id"],
        trace_run_id=uuid.UUID(state["trace_run_id"]) if state.get("trace_run_id") else None,
        request_message_id=uuid.UUID(state["user_message_id"]) if state.get("user_message_id") else None,
        parent_tool_run_id=parent_run.id if parent_run else None,
        tool_definition_id=definition.id, requested_by="conversation", capability=selection.capability,
        adapter_name=spec.adapter_name, adapter_version="1", status=status, risk_level=spec.risk_level,
        permission_required=confirmation or bool(permission and permission.policy != "not_required"),
        permission_granted=not confirmation and (permission is None or permission.policy == "not_required"),
        confirmation_required=confirmation, confirmation_summary=_confirmation_summary(selection.capability, validated or effective_arguments) if confirmation else None,
        idempotency_key=idempotency_key,
        input_schema_version=CONTRACT_VERSION, output_schema_version=CONTRACT_VERSION,
        input_json=validated or effective_arguments,
        error_json={"code": "TOOL_INPUT_INCOMPLETE", "missing_fields": missing, "validation": validation_error} if missing else {},
        max_attempts=spec.max_attempts, timeout_seconds=spec.timeout_seconds, terminal_reason=terminal_reason,
        completed_at=datetime.now(timezone.utc) if status == "blocked" else None,
        evidence_refs=[{"type": "selection", "provider": selection.provider_name, "model": selection.model_name, "confidence": selection.confidence, "rationale": selection.rationale}],
        metadata_={
            "room_turn_id": state.get("room_turn_id"),
            "room_turn_step_id": state.get("room_turn_step_id"),
            "changed_fields": selection.changed_fields,
            "continues_tool_run": bool(parent_run),
        },
    )
    session.add(run)
    session.flush()
    return run


def _room_tool_scope_valid(session: Session, conversation: Conversation | None, companion_id: uuid.UUID, state: ConversationAgentState) -> bool:
    if conversation is None or not state.get("room_turn_id") or not state.get("room_turn_step_id"):
        return False
    try:
        turn = session.get(CompanionRoomTurn, uuid.UUID(state["room_turn_id"]))
        step = session.get(CompanionRoomTurnStep, uuid.UUID(state["room_turn_step_id"]))
    except (TypeError, ValueError):
        return False
    return bool(
        turn and step and step.room_turn_id == turn.id
        and turn.conversation_id == conversation.id
        and turn.user_id == conversation.user_id
        and step.companion_id == companion_id
        and step.status == "running"
    )


def _room_tool_run_scope_valid(session: Session, conversation: Conversation | None, run: ToolRun) -> bool:
    metadata = run.metadata_ or {}
    if conversation is None or not metadata.get("room_turn_id") or not metadata.get("room_turn_step_id"):
        return False
    try:
        turn = session.get(CompanionRoomTurn, uuid.UUID(str(metadata["room_turn_id"])))
        step = session.get(CompanionRoomTurnStep, uuid.UUID(str(metadata["room_turn_step_id"])))
    except (TypeError, ValueError):
        return False
    return bool(
        turn and step and step.room_turn_id == turn.id
        and turn.conversation_id == conversation.id
        and turn.user_id == run.user_id
        and step.companion_id == run.companion_id
    )


def _complete_pending_input(session: Session, run: ToolRun, selection: SelectionResult, context: dict[str, uuid.UUID]) -> ToolRun:
    if run.capability != selection.capability:
        return run
    merged = {**(run.input_json or {}), **selection.arguments}
    merged.pop("followup_text", None)
    validated, missing, validation_error = _validate_payload(run.capability, merged, selection.missing_fields)
    run.input_json = validated or merged
    run.error_json = {"code": "TOOL_INPUT_INCOMPLETE", "missing_fields": missing, "validation": validation_error} if missing else {}
    if missing:
        return run
    run.status = "awaiting_confirmation" if run.confirmation_required else "queued"
    if run.status == "queued":
        _execute_locked(session, run)
    return run


def _confirm_locked(session: Session, run: ToolRun, context: dict[str, uuid.UUID]) -> ToolRun:
    if run.status != "awaiting_confirmation":
        raise ConversationTurnError("TOOL_RUN_NOT_CONFIRMABLE", "Only an awaiting-confirmation ToolRun can be confirmed.", {"status": run.status})
    _check_hard_stop(session, context)
    run.permission_granted = True
    run.confirmed_at = datetime.now(timezone.utc)
    run.confirmed_by = "user"
    if run.tool_definition_id:
        definition = session.get(ToolDefinition, run.tool_definition_id)
        permission = _resolve_permission(session, definition, context) if definition else None
        if permission and permission.policy == "ask_once":
            permission.scope_json = {
                **dict(permission.scope_json or {}),
                "ask_once_granted_at": run.confirmed_at.isoformat(),
            }
    run.status = "queued"
    return run


def _cancel_locked(session: Session, run: ToolRun, context: dict[str, uuid.UUID], reason: str) -> ToolRun:
    if run.status in TERMINAL_STATUSES:
        raise ConversationTurnError("TOOL_RUN_TERMINAL", "A terminal ToolRun cannot be overwritten.", {"status": run.status})
    if run.status == "running":
        run.cancel_requested_at = datetime.now(timezone.utc)
        run.terminal_reason = reason
        return run
    run.status = "cancelled"
    run.cancel_requested_at = datetime.now(timezone.utc)
    run.completed_at = datetime.now(timezone.utc)
    run.terminal_reason = reason
    return run


def _execute_locked(session: Session, run: ToolRun) -> ToolRun:
    if run.status != "queued":
        raise ConversationTurnError("TOOL_RUN_NOT_EXECUTABLE", "ToolRun is not queued for execution.", {"status": run.status})
    if run.confirmation_required and not run.permission_granted:
        raise ConversationTurnError("TOOL_CONFIRMATION_REQUIRED", "ToolRun requires explicit confirmation.")
    started = time.monotonic()
    now = datetime.now(timezone.utc)
    run.status = "running"
    run.started_at = now
    run.attempt_count += 1
    run.next_attempt_at = None
    step = ToolRunStep(tool_run_id=run.id, step_order=run.attempt_count, step_name="adapter_execution", status="running", input_json=run.input_json, started_at=now)
    session.add(step)
    session.flush()
    try:
        result = execute_adapter(session, run, run.capability, run.input_json or {})
        elapsed = int((time.monotonic() - started) * 1000)
        if elapsed > run.timeout_seconds * 1000:
            raise ToolAdapterError("TOOL_TIMEOUT", "工具执行超过允许时间。", retryable=True)
        _persist_success(session, run, step, result, elapsed)
    except ToolAdapterError as exc:
        _persist_failure(session, run, step, exc, int((time.monotonic() - started) * 1000))
    except Exception as exc:
        safe = ToolAdapterError("TOOL_ADAPTER_FAILURE", "工具执行发生未预期错误。", retryable=False, details={"error_type": type(exc).__name__})
        _persist_failure(session, run, step, safe, int((time.monotonic() - started) * 1000))
    return run


def _bounded_repair_child(
    session: Session,
    state: ConversationAgentState,
    parent: ToolRun,
    original_selection: SelectionResult,
    context: dict[str, uuid.UUID],
    *,
    step_number: int,
) -> ToolRun | None:
    """Execute at most one transparent, schema-valid repair child in this turn."""
    if parent.status != "failed" or step_number > 2:
        return None
    candidates = (parent.error_json or {}).get("details", {}).get(
        "repair_candidates", []
    )
    if not candidates or not isinstance(candidates[0], dict):
        return None
    candidate = candidates[0]
    patch = candidate.get("arguments")
    if not isinstance(patch, dict):
        return None
    arguments = {**(parent.input_json or {}), **patch}
    repair_selection = SelectionResult(
        capability=parent.capability,
        arguments=arguments,
        confidence=1.0,
        rationale=str(candidate.get("reason") or "bounded_observation_repair"),
        provider_name=original_selection.provider_name,
        model_name=original_selection.model_name,
        continues_tool_run=True,
        changed_fields=[
            str(item) for item in candidate.get("changed_fields", patch.keys())
        ],
    )
    child = _create_run(
        session,
        state,
        repair_selection,
        context,
        parent_run=parent,
        idempotency_suffix=f"repair-{step_number}",
    )
    if child.status == "queued":
        _execute_locked(session, child)
    return child


def _persist_success(session: Session, run: ToolRun, step: ToolRunStep, result: AdapterResult, elapsed: int) -> None:
    if run.status != "running":
        return
    now = datetime.now(timezone.utc)
    run.status = "succeeded"
    run.output_json = result.output
    run.error_json = {}
    run.evidence_refs = [*(run.evidence_refs or []), *result.evidence_refs]
    run.elapsed_ms = elapsed
    run.completed_at = now
    run.lease_owner = None
    run.lease_expires_at = None
    run.terminal_reason = "completed"
    step.status = "succeeded"
    step.output_json = {
        "result": result.output,
        "observation_refs": result.evidence_refs,
    }
    step.elapsed_ms = elapsed
    step.completed_at = now
    for artifact in result.artifacts:
        session.add(ToolRunArtifact(tool_run_id=run.id, **artifact))
    if run.conversation_id:
        message = Message(user_id=run.user_id, companion_id=run.companion_id, conversation_id=run.conversation_id, role="tool", content=json.dumps({"tool_run_id": str(run.id), "capability": run.capability, "status": run.status, "output": result.output}, ensure_ascii=False, default=str), content_format="json", model_provider=result.provider_name, model_name=result.model_name, metadata_={"tool_run_id": str(run.id), "capability": run.capability, "evidence_refs": result.evidence_refs})
        session.add(message)
        session.flush()
        run.result_message_id = message.id


def _persist_failure(session: Session, run: ToolRun, step: ToolRunStep, exc: ToolAdapterError, elapsed: int) -> None:
    if run.status != "running":
        return
    now = datetime.now(timezone.utc)
    retryable = exc.retryable and run.attempt_count < run.max_attempts
    run.status = "retry_scheduled" if retryable else ("timed_out" if exc.code == "TOOL_TIMEOUT" else "failed")
    run.error_json = {"code": exc.code, "message": str(exc), "retryable": retryable, "details": exc.details, "attempt": run.attempt_count}
    run.elapsed_ms = elapsed
    run.next_attempt_at = now + timedelta(seconds=min(300, 5 * (2 ** max(0, run.attempt_count - 1)))) if retryable else None
    run.completed_at = None if retryable else now
    run.lease_owner = None
    run.lease_expires_at = None
    run.terminal_reason = "retry_scheduled" if retryable else exc.code.lower()
    step.status = "failed"
    step.error_message = str(exc)
    step.output_json = {
        "code": exc.code,
        "retryable": retryable,
        "observation": exc.details,
    }
    step.elapsed_ms = elapsed
    step.completed_at = now
    if not retryable and not exc.details.get("repair_candidates"):
        session.add(BadCase(user_id=run.user_id, companion_id=run.companion_id, conversation_id=run.conversation_id, trace_run_id=run.trace_run_id, type="other", title=f"Tool failure: {run.capability}", description=f"{exc.code}: {str(exc)}", severity="high" if run.risk_level in {"high", "critical"} else "medium", status="open", evidence_links=[{"type": "tool_run", "id": str(run.id), "attempt": run.attempt_count}]))


def _ensure_definition(session: Session, capability: str) -> ToolDefinition:
    name = f"bounded_tool_{capability}"
    row = session.execute(select(ToolDefinition).where(ToolDefinition.name == name, ToolDefinition.deleted_at.is_(None))).scalar_one_or_none()
    if row:
        return row
    spec = CAPABILITIES[capability]
    row = ToolDefinition(user_id=None, companion_id=None, name=name, display_name=spec.display_name, description=spec.description, tool_type="http_api" if capability in {"search", "web_read", "weather", "exchange"} else "internal", risk_level=spec.risk_level, permission_policy="ask_every_time" if spec.side_effect else "not_required", is_enabled=True, input_schema_json=spec.input_schema, output_schema_json={"type": "object"}, config_json={"contract_version": CONTRACT_VERSION, "adapter_name": spec.adapter_name, "bounded": True})
    session.add(row)
    session.flush()
    return row


def _resolve_permission(session: Session, definition: ToolDefinition, context: dict[str, uuid.UUID]) -> ToolPermission | None:
    now = datetime.now(timezone.utc)
    permissions = session.execute(select(ToolPermission).where(ToolPermission.user_id == context["user_id"], ToolPermission.companion_id == context["companion_id"], ToolPermission.tool_definition_id == definition.id, ToolPermission.deleted_at.is_(None)).order_by(ToolPermission.created_at.desc())).scalars().all()
    for permission in permissions:
        if permission.allowed_until and permission.allowed_until <= now:
            permission.status = "expired"
            continue
        if permission.status in {"active", "denied", "revoked"}:
            return permission
    permission = ToolPermission(
        user_id=context["user_id"],
        companion_id=context["companion_id"],
        tool_definition_id=definition.id,
        policy=definition.permission_policy,
        status="active",
        reason="bounded_tool_default_companion_scope",
        scope_json={"conversation_scoped_execution": True},
    )
    session.add(permission)
    session.flush()
    return permission


def _check_hard_stop(session: Session, context: dict[str, uuid.UUID]) -> None:
    active = session.execute(select(ScopedHardStopEvent).where(ScopedHardStopEvent.user_id == context["user_id"], ScopedHardStopEvent.companion_id == context["companion_id"], ScopedHardStopEvent.hard_stop_status == "active").limit(1)).scalar_one_or_none()
    if active:
        raise ConversationTurnError("TOOL_HARD_STOP_ACTIVE", "Companion hard stop is active; tool execution is blocked.", {"hard_stop_event_id": str(active.id)})


def _validate_payload(capability: str, payload: dict[str, Any], declared_missing: list[str]) -> tuple[dict[str, Any], list[str], list[dict[str, Any]]]:
    model = CAPABILITIES[capability].input_model
    try:
        value = model.model_validate(payload)
        return value.model_dump(mode="json"), [], []
    except ValidationError as exc:
        errors = exc.errors(include_url=False, include_context=False, include_input=False)
        missing = sorted({str(item["loc"][0]) for item in errors if item.get("type") == "missing"} | set(declared_missing))
        return {}, missing or [str(item["loc"][0]) for item in errors], errors


def _confirmation_summary(capability: str, payload: dict[str, Any]) -> str:
    labels = {"reminder": "创建提醒", "calendar": "写入本地日程", "note": "保存轻量笔记", "file": "创建受限文件副本"}
    title = payload.get("title") or payload.get("output_title") or payload.get("file_document_id") or "未命名"
    when = payload.get("due_at") or payload.get("starts_at")
    return f"{labels.get(capability, '执行工具写操作')}：{title}" + (f"；时间 {when}" if when else "")


def _apply_run_to_state(
    state: ConversationAgentState,
    run: ToolRun,
    selection: SelectionResult,
    *,
    runs: list[ToolRun] | None = None,
    parent_run: ToolRun | None = None,
) -> None:
    projection = _run_projection(run)
    chain = runs or [run]
    state["tool_runs"] = [_run_projection(item) for item in chain]
    state["tool_run_ids"] = [str(item.id) for item in chain]
    state["tool_context"] = projection
    changed_fields = set(
        (run.metadata_ or {}).get("changed_fields") or selection.changed_fields
    )
    parent_projection = next(
        (
            _run_projection(item)
            for item in chain
            if item.id == run.parent_tool_run_id
        ),
        _run_projection(parent_run),
    )
    slots = {
        key: {
            "value": value,
            "status": (
                "confirmed"
                if key in changed_fields or not run.parent_tool_run_id
                else "inherited"
            ),
            "source_message_id": (
                str(run.request_message_id)
                if key in changed_fields or not run.parent_tool_run_id
                else parent_projection.get("request_message_id")
            ),
        }
        for key, value in (run.input_json or {}).items()
    }
    state["tool_intent"] = {
        "capability": run.capability,
        "status": (
            "complete"
            if run.status == "succeeded"
            else ("awaiting_input" if run.status == "awaiting_input" else "repairable")
        ),
        "slots": slots,
        "unresolved_fields": projection.get("missing_fields", []),
        "parent_tool_run_id": projection.get("parent_tool_run_id"),
        "changed_fields": list(changed_fields),
        "continues_prior_run": bool(projection.get("parent_tool_run_id")),
    }
    state["tool_observations"] = [
        {
            "tool_run_id": str(item.id),
            "parent_tool_run_id": (
                str(item.parent_tool_run_id) if item.parent_tool_run_id else None
            ),
            "status": item.status,
            "output": item.output_json or {},
            "error": item.error_json or {},
        }
        for item in chain
    ]
    state["tool_loop"] = {
        "contract_version": "bounded_observe_replan_v1",
        "run_count": len(chain),
        "max_runs": 3,
        "repair_count": max(0, len(chain) - 1),
        "terminal_status": run.status,
        "reasoning_content_persisted": False,
    }
    state.setdefault("trace_steps", []).append({"step": "tool_selection", "order": 45, "status": "completed", "tool_run_id": str(run.id), "capability": run.capability, "run_status": run.status, "confidence": selection.confidence, "rationale": selection.rationale})
    state.setdefault("trace_steps", []).append({"step": "tool_execution", "order": 46, "status": "completed" if run.status == "succeeded" else run.status, "tool_run_id": str(run.id), "attempt_count": run.attempt_count, "evidence_refs": run.evidence_refs or [], "error": run.error_json or {}})


def _run_projection(run: ToolRun | None) -> dict[str, Any]:
    if run is None:
        return {}
    return {"id": str(run.id), "user_id": str(run.user_id), "companion_id": str(run.companion_id), "conversation_id": str(run.conversation_id) if run.conversation_id else None, "tool_definition_id": str(run.tool_definition_id) if run.tool_definition_id else None, "parent_tool_run_id": str(run.parent_tool_run_id) if run.parent_tool_run_id else None, "requested_by": run.requested_by, "capability": run.capability, "adapter_name": run.adapter_name, "adapter_version": run.adapter_version, "status": run.status, "risk_level": run.risk_level, "permission_required": run.permission_required, "permission_granted": run.permission_granted, "confirmation_required": run.confirmation_required, "confirmation_summary": run.confirmation_summary, "input_json": run.input_json or {}, "output_json": run.output_json or {}, "error_json": run.error_json or {}, "missing_fields": (run.error_json or {}).get("missing_fields", []), "evidence_refs": run.evidence_refs or [], "attempt_count": run.attempt_count, "max_attempts": run.max_attempts, "timeout_seconds": run.timeout_seconds, "next_attempt_at": run.next_attempt_at.isoformat() if run.next_attempt_at else None, "terminal_reason": run.terminal_reason, "request_message_id": str(run.request_message_id) if run.request_message_id else None, "result_message_id": str(run.result_message_id) if run.result_message_id else None, "created_at": run.created_at.isoformat() if run.created_at else None, "completed_at": run.completed_at.isoformat() if run.completed_at else None}


def _reconcile_conversation_task(tool_run_id: uuid.UUID) -> None:
    try:
        from app.services.conversation_task_runtime_service import (
            reconcile_task_for_tool_run,
        )

        reconcile_task_for_tool_run(tool_run_id)
    except Exception:
        # ToolRun is authoritative and durable. The Task scheduler retries
        # reconciliation without changing the Tool terminal result.
        return


def _selection_projection(run: ToolRun | None) -> dict[str, Any] | None:
    if run is None:
        return None
    error = run.error_json or {}
    return {
        "id": str(run.id),
        "parent_tool_run_id": (
            str(run.parent_tool_run_id) if run.parent_tool_run_id else None
        ),
        "capability": run.capability,
        "status": run.status,
        "input_json": run.input_json or {},
        "error_code": error.get("code"),
        "missing_fields": error.get("missing_fields", []),
        "request_message_id": (
            str(run.request_message_id) if run.request_message_id else None
        ),
    }
