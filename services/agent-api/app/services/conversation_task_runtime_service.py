"""Durable, bounded orchestration for explicit multi-step Conversation tasks."""

from __future__ import annotations

import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.providers.base import LLMProviderError
from app.agents.providers.openai_compatible import OpenAICompatibleProvider
from app.agents.state import ConversationAgentState
from app.db.models import (
    Conversation,
    ConversationTaskPlanRevision,
    ConversationTaskRun,
    ConversationTaskStep,
    ConversationTaskStepAttempt,
    ScopedHardStopEvent,
    ToolRun,
)
from app.services.conversation_service import (
    ConversationTurnError,
    get_session,
    is_companion_room_conversation,
)
from app.services.tool_runtime_service import (
    execute_task_tool_step,
    request_task_tool_cancellation,
)
from app.tasks.planning import TaskPlan, plan_task, replan_step
from app.tools.selection import confirmation_action


ACTIVE_TASK_STATUSES = {
    "draft", "awaiting_input", "awaiting_approval", "ready", "running", "paused", "blocked"
}
TERMINAL_TASK_STATUSES = {"completed", "cancelled", "failed"}
TERMINAL_STEP_STATUSES = {"succeeded", "failed", "blocked", "cancelled", "skipped"}
MAX_ORCHESTRATION_ACTIONS_PER_TURN = 6
_PAUSE = re.compile(r"^(暂停|先停一下|pause)(?:任务)?[。.!！]?$", re.I)
_RESUME = re.compile(r"^(继续|恢复|resume)(?:任务|执行)?[。.!！]?$", re.I)
_CANCEL = re.compile(r"^(取消|停止|终止|cancel|stop)(?:任务|执行)?[。.!！]?$", re.I)
_REVISE = re.compile(
    r"(把|将)?(?:这个|当前)?任务(?:目标|计划)?(?:改成|改为|调整为|修改为)|"
    r"\b(?:change|revise|update)\s+(?:the\s+)?(?:task|goal|plan)\b",
    re.I,
)


def process_conversation_task_turn(
    state: ConversationAgentState,
) -> ConversationAgentState:
    """Create or advance one scoped TaskRun, without routing ordinary turns."""
    lease_owner = _turn_lease_owner(state)
    task = _find_active_task(state)
    if task is None:
        plan = plan_task(
            state.get("user_input", ""),
            recent_messages=state.get("recent_messages", []),
        )
        if not plan.should_plan:
            _trace(state, "skipped", plan.rationale)
            state["task_runtime_handled"] = False
            return state
        with get_session() as session:
            context = _scope_context(session, state)
            task = _find_active_task_in_session(session, context)
            if task is None:
                task = _create_task(session, state, context, plan)
            if _claim_task_lease(session, task, lease_owner):
                try:
                    _execute_task(session, state, task)
                finally:
                    _release_task_lease(task, lease_owner)
            session.commit()
            _project_to_state(session, state, task)
        state["task_runtime_handled"] = True
        return state

    with get_session() as session:
        task = session.get(ConversationTaskRun, task.id, with_for_update=True)
        if task is None:
            state["task_runtime_handled"] = False
            return state
        _check_scope(task, state)
        lease_claimed = _claim_task_lease(session, task, lease_owner)
        text = state.get("user_input", "").strip()
        action = _task_action(text)
        if action == "cancel":
            _cancel_task(session, task, "user_cancelled")
        elif action == "pause":
            _pause_task(task, "user_paused")
        elif action == "resume":
            _resume_task(task)
            if lease_claimed:
                _execute_task(session, state, task)
        elif task.status == "awaiting_approval" and confirmation_action(text):
            # The existing Tool Runtime owns confirmation. Reconcile after it runs.
            state["task_runtime_handled"] = False
        elif task.status in {"awaiting_input", "blocked"}:
            repaired = _attempt_replan(
                session,
                task,
                trigger="user_correction",
                user_input=text,
                source_message_id=uuid.UUID(state["user_message_id"]),
            )
            if repaired:
                if lease_claimed:
                    _execute_task(session, state, task)
                state["task_runtime_handled"] = True
            else:
                state["task_runtime_handled"] = task.status == "awaiting_input"
        elif _REVISE.search(text):
            repaired = _attempt_replan(
                session,
                task,
                trigger="user_goal_correction",
                user_input=text,
                source_message_id=uuid.UUID(state["user_message_id"]),
            )
            if repaired:
                if lease_claimed:
                    _execute_task(session, state, task)
                state["task_runtime_handled"] = True
            else:
                state["task_runtime_handled"] = task.status == "awaiting_input"
        elif task.status in {"ready", "running"}:
            if lease_claimed:
                _execute_task(session, state, task)
            state["task_runtime_handled"] = True
        else:
            # A paused/blocked task remains visible but does not capture ordinary chat.
            state["task_runtime_handled"] = False
        if lease_claimed:
            _release_task_lease(task, lease_owner)
        session.commit()
        _project_to_state(session, state, task)
    return state


def reconcile_conversation_task_turn(
    state: ConversationAgentState,
) -> ConversationAgentState:
    """Reconcile ToolRun truth after normal confirmation/retry processing."""
    task_id = (state.get("task_run") or {}).get("id")
    if not task_id:
        return state
    with get_session() as session:
        task = session.get(
            ConversationTaskRun, uuid.UUID(str(task_id)), with_for_update=True
        )
        if task is None or task.status in TERMINAL_TASK_STATUSES:
            return state
        _check_scope(task, state)
        lease_owner = _turn_lease_owner(state)
        if _claim_task_lease(session, task, lease_owner):
            try:
                _execute_task(session, state, task)
            finally:
                _release_task_lease(task, lease_owner)
        session.commit()
        _project_to_state(session, state, task)
    return state


def list_task_runs(
    *,
    companion_id: uuid.UUID,
    conversation_id: uuid.UUID,
    status: str | None = None,
) -> list[dict[str, Any]]:
    with get_session() as session:
        statement = select(ConversationTaskRun).where(
            ConversationTaskRun.companion_id == companion_id,
            ConversationTaskRun.conversation_id == conversation_id,
            ConversationTaskRun.deleted_at.is_(None),
        )
        if status:
            statement = statement.where(ConversationTaskRun.status == status)
        rows = session.execute(
            statement.order_by(ConversationTaskRun.created_at.desc()).limit(50)
        ).scalars().all()
        return [_task_projection(session, row) for row in rows]


def get_task_run(
    task_run_id: uuid.UUID,
    *,
    companion_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> dict[str, Any] | None:
    with get_session() as session:
        task = session.get(ConversationTaskRun, task_run_id)
        if task is None:
            return None
        if task.companion_id != companion_id or task.conversation_id != conversation_id:
            raise ConversationTurnError(
                "TASK_SCOPE_MISMATCH", "TaskRun does not belong to this Conversation."
            )
        return _task_projection(session, task)


def task_action(
    task_run_id: uuid.UUID,
    *,
    companion_id: uuid.UUID,
    conversation_id: uuid.UUID,
    action: str,
) -> dict[str, Any] | None:
    with get_session() as session:
        task = session.get(ConversationTaskRun, task_run_id, with_for_update=True)
        if task is None:
            return None
        if task.companion_id != companion_id or task.conversation_id != conversation_id:
            raise ConversationTurnError(
                "TASK_SCOPE_MISMATCH", "TaskRun does not belong to this Conversation."
            )
        if action == "pause":
            _pause_task(task, "user_paused")
        elif action == "resume":
            _resume_task(task)
        elif action == "cancel":
            _cancel_task(session, task, "user_cancelled")
        else:
            raise ConversationTurnError(
                "TASK_ACTION_INVALID", "Task action must be pause, resume, or cancel."
            )
        session.commit()
        return _task_projection(session, task)


def reconcile_task_for_tool_run(tool_run_id: uuid.UUID) -> None:
    """Advance the owning TaskRun after the durable Tool retry worker settles."""
    with get_session() as session:
        attempt = session.execute(
            select(ConversationTaskStepAttempt)
            .where(ConversationTaskStepAttempt.tool_run_id == tool_run_id)
            .limit(1)
        ).scalar_one_or_none()
        if attempt is None:
            return
        step = session.get(ConversationTaskStep, attempt.task_step_id)
        task = (
            session.get(ConversationTaskRun, step.task_run_id, with_for_update=True)
            if step is not None
            else None
        )
        if task is None or task.status in TERMINAL_TASK_STATUSES:
            return
        lease_owner = f"tool-retry:{tool_run_id}"
        if not _claim_task_lease(session, task, lease_owner):
            return
        state: ConversationAgentState = {
            "user_id": str(task.user_id),
            "companion_id": str(task.companion_id),
            "conversation_id": str(task.conversation_id),
            "user_message_id": str(task.source_message_id),
            "trace_run_id": str(task.trace_run_id) if task.trace_run_id else "",
            "turn_idempotency_key": (
                f"task-recovery:{task.id}:plan-{task.plan_version}:"
                f"revision-{task.revision}"
            ),
            "user_input": task.goal,
            "trace_steps": [],
            "tool_runs": [],
            "tool_run_ids": [],
        }
        try:
            _execute_task(session, state, task)
        finally:
            _release_task_lease(task, lease_owner)
            session.commit()


def ensure_task_tool_confirmation_allowed(
    session: Session,
    tool_run_id: uuid.UUID,
) -> None:
    """Prevent a paused/cancelled TaskRun from being bypassed via Tool controls."""
    attempt = session.execute(
        select(ConversationTaskStepAttempt)
        .where(ConversationTaskStepAttempt.tool_run_id == tool_run_id)
        .limit(1)
    ).scalar_one_or_none()
    if attempt is None:
        return
    step = session.get(ConversationTaskStep, attempt.task_step_id)
    task = session.get(ConversationTaskRun, step.task_run_id) if step else None
    if task is None:
        return
    if task.status == "paused":
        raise ConversationTurnError(
            "TASK_RUN_PAUSED",
            "Resume the TaskRun before confirming its pending tool step.",
        )
    if task.status in TERMINAL_TASK_STATUSES:
        raise ConversationTurnError(
            "TASK_RUN_TERMINAL",
            "A terminal TaskRun cannot execute a pending tool step.",
            {"status": task.status},
        )
    context = {
        "user_id": task.user_id,
        "companion_id": task.companion_id,
        "conversation_id": task.conversation_id,
    }
    _check_hard_stop(session, context)


def reconcile_active_tasks(*, limit: int = 10) -> dict[str, int]:
    """Recover ready/running TaskRuns without touching paused or approval-gated work."""
    counts = {"claimed": 0, "completed": 0, "active": 0, "failed": 0}
    worker_id = f"task-scheduler:{uuid.uuid4()}"
    now = datetime.now(timezone.utc)
    with get_session() as session:
        tasks = list(session.execute(
            select(ConversationTaskRun)
            .where(
                ConversationTaskRun.status.in_({"ready", "running"}),
                ConversationTaskRun.deleted_at.is_(None),
                (
                    ConversationTaskRun.lease_expires_at.is_(None)
                    | (ConversationTaskRun.lease_expires_at <= now)
                ),
            )
            .order_by(ConversationTaskRun.updated_at)
            .limit(limit)
            .with_for_update(skip_locked=True)
        ).scalars().all())
        for task in tasks:
            _claim_task_lease(session, task, worker_id)
        task_ids = [task.id for task in tasks]
        session.commit()
    counts["claimed"] = len(task_ids)
    for task_id in task_ids:
        try:
            with get_session() as session:
                task = session.get(
                    ConversationTaskRun,
                    task_id,
                    with_for_update=True,
                )
                if task is None or task.status not in {"ready", "running"}:
                    continue
                if task.lease_owner != worker_id:
                    continue
                state: ConversationAgentState = {
                    "user_id": str(task.user_id),
                    "companion_id": str(task.companion_id),
                    "conversation_id": str(task.conversation_id),
                    "user_message_id": str(task.source_message_id),
                    "trace_run_id": (
                        str(task.trace_run_id) if task.trace_run_id else ""
                    ),
                    "turn_idempotency_key": (
                        f"task-scheduler:{task.id}:plan-{task.plan_version}:"
                        f"revision-{task.revision}"
                    ),
                    "user_input": task.goal,
                    "trace_steps": [],
                    "tool_runs": [],
                    "tool_run_ids": [],
                }
                try:
                    _execute_task(session, state, task)
                finally:
                    _release_task_lease(task, worker_id)
                    session.commit()
                counts[
                    "completed"
                    if task.status == "completed"
                    else "active"
                ] += 1
        except Exception:
            counts["failed"] += 1
            with get_session() as session:
                task = session.get(ConversationTaskRun, task_id, with_for_update=True)
                if task is not None:
                    _release_task_lease(task, worker_id)
                    session.commit()
    return counts


def _turn_lease_owner(state: ConversationAgentState) -> str:
    trace_run_id = str(state.get("trace_run_id") or "unknown")
    return f"conversation-turn:{trace_run_id}"[:120]


def _claim_task_lease(
    session: Session,
    task: ConversationTaskRun,
    owner: str,
    *,
    lease_seconds: int = 120,
) -> bool:
    """Claim one TaskRun across commits made around external tool execution."""
    now = datetime.now(timezone.utc)
    if (
        task.lease_owner
        and task.lease_owner != owner
        and task.lease_expires_at
        and task.lease_expires_at > now
    ):
        return False
    task.lease_owner = owner
    task.lease_expires_at = now + timedelta(seconds=max(30, lease_seconds))
    session.flush()
    return True


def _release_task_lease(task: ConversationTaskRun, owner: str) -> None:
    if task.lease_owner != owner:
        return
    task.lease_owner = None
    task.lease_expires_at = None


def _find_active_task(
    state: ConversationAgentState,
) -> ConversationTaskRun | None:
    with get_session() as session:
        context = _scope_context(session, state)
        task = _find_active_task_in_session(session, context)
        if task is not None:
            session.expunge(task)
        return task


def _find_active_task_in_session(
    session: Session,
    context: dict[str, uuid.UUID],
) -> ConversationTaskRun | None:
    return session.execute(
        select(ConversationTaskRun)
        .where(
            ConversationTaskRun.user_id == context["user_id"],
            ConversationTaskRun.companion_id == context["companion_id"],
            ConversationTaskRun.conversation_id == context["conversation_id"],
            ConversationTaskRun.status.in_(ACTIVE_TASK_STATUSES),
            ConversationTaskRun.deleted_at.is_(None),
        )
        .order_by(ConversationTaskRun.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _create_task(
    session: Session,
    state: ConversationAgentState,
    context: dict[str, uuid.UUID],
    plan: TaskPlan,
) -> ConversationTaskRun:
    _check_hard_stop(session, context)
    idempotency_key = str(
        state.get("turn_idempotency_key") or state.get("trace_run_id")
    )
    existing = session.execute(
        select(ConversationTaskRun).where(
            ConversationTaskRun.user_id == context["user_id"],
            ConversationTaskRun.companion_id == context["companion_id"],
            ConversationTaskRun.conversation_id == context["conversation_id"],
            ConversationTaskRun.idempotency_key == idempotency_key,
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    task = ConversationTaskRun(
        user_id=context["user_id"],
        companion_id=context["companion_id"],
        conversation_id=context["conversation_id"],
        source_message_id=uuid.UUID(state["user_message_id"]),
        trace_run_id=uuid.UUID(state["trace_run_id"]) if state.get("trace_run_id") else None,
        goal=plan.goal,
        status="ready",
        acceptance_state="pending",
        idempotency_key=idempotency_key,
        token_count=int(plan.token_usage.get("total_tokens") or 0),
        metadata_={
            "planner": {
                "provider": plan.provider_name,
                "model": plan.model_name,
                "rationale": plan.rationale,
                "token_usage": plan.token_usage,
            },
            "contract_version": "conversation-task-runtime.v1",
            "reasoning_content_persisted": False,
        },
    )
    session.add(task)
    session.flush()
    for planned in plan.steps:
        session.add(ConversationTaskStep(
            task_run_id=task.id,
            step_order=planned.order,
            title=planned.title,
            executor_type=planned.executor_type,
            capability=planned.capability,
            risk_level=planned.risk_level,
            status="pending",
            dependencies_json=planned.dependencies,
            input_json=planned.arguments,
            acceptance_criteria_json=planned.acceptance_criteria,
            confirmation_required=planned.confirmation_required,
        ))
    session.add(ConversationTaskPlanRevision(
        task_run_id=task.id,
        version=1,
        previous_version=None,
        trigger="initial_user_goal",
        goal=task.goal,
        plan_json=_plan_snapshot(plan),
        changes_json={"created": True},
        approval_required=any(step.confirmation_required for step in plan.steps),
        created_by="planner",
        source_message_id=task.source_message_id,
        metadata_={"provider": plan.provider_name, "model": plan.model_name},
    ))
    session.flush()
    return task


def _execute_task(
    session: Session,
    state: ConversationAgentState,
    task: ConversationTaskRun,
) -> None:
    if task.status in {"paused", "cancelled", "completed", "failed"}:
        return
    context = {
        "user_id": task.user_id,
        "companion_id": task.companion_id,
        "conversation_id": task.conversation_id,
    }
    if _hard_stop_active(session, context):
        _cancel_task(session, task, "hard_stop_active")
        return
    _recover_expired_attempts(session, task)
    _sync_tool_attempts(session, task)
    if any(step.status == "cancelled" for step in _steps(session, task.id)):
        _cancel_task(session, task, "tool_step_cancelled")
        return
    if task.status == "awaiting_approval":
        return
    task.status = "running"
    task.started_at = task.started_at or datetime.now(timezone.utc)
    for _ in range(MAX_ORCHESTRATION_ACTIONS_PER_TURN):
        steps = _steps(session, task.id)
        _mark_ready_steps(steps)
        if any(step.status == "awaiting_approval" for step in steps):
            task.status = "awaiting_approval"
            task.stop_reason = "tool_confirmation_required"
            return
        ready_steps = [step for step in steps if step.status == "ready"]
        research_batch = [
            step for step in ready_steps
            if step.executor_type == "research" and step.risk_level == "low"
        ][:2]
        if len(research_batch) == 2:
            _execute_research_batch(session, task, research_batch, steps)
            session.flush()
            continue
        ready = ready_steps[0] if ready_steps else None
        if ready is None:
            if all(step.status in {"succeeded", "skipped"} for step in steps):
                task.status = "completed"
                task.acceptance_state = (
                    "verified"
                    if any(
                        step.executor_type == "verify" and step.status == "succeeded"
                        for step in steps
                    )
                    else "not_applicable"
                )
                task.completed_at = datetime.now(timezone.utc)
                task.current_step_order = None
                task.stop_reason = "completed"
            elif failed := next(
                (step for step in steps if step.status in {"failed", "blocked"}),
                None,
            ):
                if _attempt_replan(
                    session,
                    task,
                    trigger="structured_step_failure",
                    failed_step=failed,
                ):
                    continue
                if task.status == "awaiting_input":
                    return
                task.status = "blocked"
                task.acceptance_state = "rejected"
                task.stop_reason = "step_failed_replan_exhausted"
            return
        task.current_step_order = ready.step_order
        if ready.executor_type == "tool":
            _execute_tool_step(session, state, task, ready)
        elif ready.executor_type == "research":
            _execute_research_step(session, task, ready, steps)
        else:
            _execute_verify_step(session, task, ready, steps)
        session.flush()
        if ready.status == "awaiting_approval":
            task.status = "awaiting_approval"
            task.stop_reason = "step_awaiting_approval"
            return
        if ready.status == "awaiting_input":
            task.status = "awaiting_input"
            task.stop_reason = "step_awaiting_input"
            return
        if ready.status in {"failed", "blocked"}:
            if _attempt_replan(
                session,
                task,
                trigger="structured_step_failure",
                failed_step=ready,
            ):
                continue
            if task.status == "awaiting_input":
                return
            task.status = "blocked"
            task.acceptance_state = "rejected"
            task.stop_reason = "step_failed_replan_exhausted"
            return
    steps = _steps(session, task.id)
    _mark_ready_steps(steps)
    if all(step.status in {"succeeded", "skipped"} for step in steps):
        task.status = "completed"
        task.acceptance_state = (
            "verified"
            if any(
                step.executor_type == "verify" and step.status == "succeeded"
                for step in steps
            )
            else "not_applicable"
        )
        task.completed_at = datetime.now(timezone.utc)
        task.current_step_order = None
        task.stop_reason = "completed"
    else:
        task.status = "paused"
        task.paused_at = datetime.now(timezone.utc)
        task.stop_reason = "turn_action_budget_exhausted"


def _execute_tool_step(
    session: Session,
    state: ConversationAgentState,
    task: ConversationTaskRun,
    step: ConversationTaskStep,
) -> None:
    if task.tool_run_count >= task.max_tool_runs:
        step.status = "blocked"
        step.error_json = {"code": "TASK_TOOL_BUDGET_EXHAUSTED"}
        return
    step.attempt_count += 1
    step.status = "running"
    step.started_at = step.started_at or datetime.now(timezone.utc)
    attempt = ConversationTaskStepAttempt(
        task_step_id=step.id,
        attempt_number=step.attempt_count,
        executor_type="tool",
        status="running",
        trace_run_id=task.trace_run_id,
        input_summary=_bounded_json(step.input_json),
        lease_owner=f"conversation-turn:{state.get('trace_run_id')}",
        lease_expires_at=datetime.now(timezone.utc) + timedelta(seconds=step.timeout_seconds + 10),
        started_at=datetime.now(timezone.utc),
    )
    session.add(attempt)
    session.flush()
    # Persist the lease before entering the external Tool adapter. A restart can
    # then reconcile the linked ToolRun or expire this attempt without replaying
    # an unrecorded side effect.
    session.commit()
    run = execute_task_tool_step(
        session,
        state,
        capability=str(step.capability),
        arguments=step.input_json or {},
        task_step_id=step.id,
        attempt_number=step.attempt_count,
    )
    task.tool_run_count += 1
    attempt.tool_run_id = run.id
    _apply_tool_run_to_step(step, attempt, run)


def _sync_tool_attempts(session: Session, task: ConversationTaskRun) -> None:
    steps = _steps(session, task.id)
    for step in steps:
        if step.executor_type != "tool" or step.status not in {
            "running", "awaiting_input", "awaiting_approval"
        }:
            continue
        attempt = session.execute(
            select(ConversationTaskStepAttempt)
            .where(ConversationTaskStepAttempt.task_step_id == step.id)
            .order_by(ConversationTaskStepAttempt.attempt_number.desc())
            .limit(1)
        ).scalar_one_or_none()
        if attempt is None or attempt.tool_run_id is None:
            continue
        run = session.get(ToolRun, attempt.tool_run_id)
        if run is not None:
            _apply_tool_run_to_step(step, attempt, run)
    if not any(step.status == "awaiting_approval" for step in steps):
        if task.status == "awaiting_approval":
            task.status = "running"
            task.stop_reason = None


def _recover_expired_attempts(
    session: Session,
    task: ConversationTaskRun,
) -> None:
    """Recover only expired leases; live work is never stolen or duplicated."""
    now = datetime.now(timezone.utc)
    attempts = session.execute(
        select(ConversationTaskStepAttempt).where(
            ConversationTaskStepAttempt.status == "running",
            ConversationTaskStepAttempt.lease_expires_at.is_not(None),
            ConversationTaskStepAttempt.lease_expires_at <= now,
            ConversationTaskStepAttempt.task_step_id.in_(
                select(ConversationTaskStep.id).where(
                    ConversationTaskStep.task_run_id == task.id
                )
            ),
        )
    ).scalars().all()
    for attempt in attempts:
        step = session.get(ConversationTaskStep, attempt.task_step_id)
        if step is None:
            continue
        if attempt.tool_run_id:
            run = session.get(ToolRun, attempt.tool_run_id)
            if run is not None and run.status in {
                "succeeded", "failed", "timed_out", "blocked", "cancelled",
                "awaiting_confirmation", "awaiting_input",
            }:
                _apply_tool_run_to_step(step, attempt, run)
                continue
            if run is not None and run.status in {
                "queued", "running", "retry_scheduled"
            }:
                wait_until = run.next_attempt_at or run.lease_expires_at or now
                attempt.lease_expires_at = wait_until + timedelta(
                    seconds=run.timeout_seconds + 10
                )
                continue
        attempt.status = "timed_out"
        attempt.error_json = {"code": "TASK_STEP_LEASE_EXPIRED"}
        attempt.completed_at = now
        attempt.lease_owner = None
        attempt.lease_expires_at = None
        step.status = "failed"
        step.error_json = {"code": "TASK_STEP_LEASE_EXPIRED"}
        step.completed_at = now


def _attempt_replan(
    session: Session,
    task: ConversationTaskRun,
    *,
    trigger: str,
    failed_step: ConversationTaskStep | None = None,
    user_input: str | None = None,
    source_message_id: uuid.UUID | None = None,
) -> bool:
    if task.replan_count >= task.max_replans:
        task.stop_reason = "replan_budget_exhausted"
        return False
    steps = _steps(session, task.id)
    target = failed_step or next(
        (
            item
            for item in steps
            if item.status in {"awaiting_input", "failed", "blocked", "ready", "pending"}
        ),
        None,
    )
    if target is None:
        return False
    if target.attempt_count >= target.max_attempts and target.status != "awaiting_input":
        task.stop_reason = "step_attempt_budget_exhausted"
        return False
    completed = [
        {
            "order": item.step_order,
            "title": item.title,
            "status": item.status,
            "output": _safe_observation(item.output_json),
            "evidence_refs": (item.evidence_refs or [])[:8],
        }
        for item in steps
        if item.status == "succeeded"
    ]
    decision = replan_step(
        goal=task.goal,
        step={
            "order": target.step_order,
            "title": target.title,
            "executor_type": target.executor_type,
            "capability": target.capability,
            "arguments": _safe_observation(target.input_json),
            "status": target.status,
            "error": _safe_observation(target.error_json),
            "acceptance_criteria": target.acceptance_criteria_json or [],
            "attempt_count": target.attempt_count,
            "max_attempts": target.max_attempts,
        },
        completed_steps=completed,
        trigger=trigger,
        user_input=user_input,
    )
    task.replan_count += 1
    task.token_count += int(decision.token_usage.get("total_tokens") or 0)
    if task.token_count > task.max_tokens:
        task.status = "blocked"
        task.stop_reason = "task_token_budget_exhausted"
        return False
    previous_goal = task.goal
    previous_arguments = dict(target.input_json or {})
    previous_status = target.status
    if decision.goal:
        task.goal = decision.goal
    if decision.acceptance_criteria:
        target.acceptance_criteria_json = decision.acceptance_criteria
    if decision.action == "retry":
        target.input_json = decision.arguments
        target.status = "ready"
        target.error_json = {}
        target.completed_at = None
        _reset_dependency_blocks(steps, target.step_order)
        task.status = "ready"
        task.acceptance_state = "pending"
        task.stop_reason = None
    elif decision.action == "await_input":
        target.status = "awaiting_input"
        target.error_json = {
            **(target.error_json or {}),
            "code": "TASK_INPUT_REQUIRED",
        }
        task.status = "awaiting_input"
        task.stop_reason = "replan_awaiting_input"
    else:
        task.status = "blocked"
        task.stop_reason = decision.rationale or "replan_stopped"
    previous_version = task.plan_version
    task.plan_version += 1
    task.revision += 1
    session.add(ConversationTaskPlanRevision(
        task_run_id=task.id,
        version=task.plan_version,
        previous_version=previous_version,
        trigger=trigger,
        goal=task.goal,
        plan_json=_current_plan_snapshot(steps),
        changes_json={
            "step_order": target.step_order,
            "action": decision.action,
            "rationale": decision.rationale,
            "previous_status": previous_status,
            "goal_changed": task.goal != previous_goal,
            "arguments_changed": decision.arguments != previous_arguments,
            "completed_steps_reused": [item["order"] for item in completed],
        },
        approval_required=bool(
            target.confirmation_required and decision.action == "retry"
        ),
        created_by="replanner",
        source_message_id=source_message_id,
        metadata_={
            "provider": decision.provider_name,
            "model": decision.model_name,
            "token_usage": decision.token_usage,
            "reasoning_content_persisted": False,
        },
    ))
    session.flush()
    return decision.action == "retry"


def _reset_dependency_blocks(
    steps: list[ConversationTaskStep],
    repaired_order: int,
) -> None:
    for item in steps:
        if (
            item.status == "blocked"
            and repaired_order in set(item.dependencies_json or [])
            and (item.error_json or {}).get("code") == "TASK_DEPENDENCY_FAILED"
        ):
            item.status = "pending"
            item.error_json = {}
            item.completed_at = None


def _current_plan_snapshot(
    steps: list[ConversationTaskStep],
) -> dict[str, Any]:
    return {
        "steps": [
            {
                "order": item.step_order,
                "title": item.title,
                "executor_type": item.executor_type,
                "capability": item.capability,
                "arguments": _safe_observation(item.input_json),
                "dependencies": item.dependencies_json or [],
                "risk_level": item.risk_level,
                "acceptance_criteria": item.acceptance_criteria_json or [],
                "confirmation_required": item.confirmation_required,
                "status": item.status,
            }
            for item in steps[:6]
        ]
    }


def _apply_tool_run_to_step(
    step: ConversationTaskStep,
    attempt: ConversationTaskStepAttempt,
    run: ToolRun,
) -> None:
    if run.status == "succeeded":
        step.status = "succeeded"
        step.output_json = _safe_observation(run.output_json)
        step.evidence_refs = [
            {"type": "tool_run", "id": str(run.id)},
            *(run.evidence_refs or []),
        ]
        step.error_json = {}
        step.completed_at = run.completed_at or datetime.now(timezone.utc)
        attempt.status = "succeeded"
        attempt.observation_json = step.output_json
        attempt.verification_json = {
            "status": "accepted",
            "criteria_count": len(step.acceptance_criteria_json or []),
            "evidence_present": True,
        }
        attempt.completed_at = step.completed_at
    elif run.status == "awaiting_confirmation":
        step.status = "awaiting_approval"
        attempt.status = "awaiting_approval"
        attempt.observation_json = {
            "tool_run_id": str(run.id),
            "confirmation_summary": run.confirmation_summary,
        }
    elif run.status == "awaiting_input":
        step.status = "awaiting_input"
        attempt.status = "failed"
        attempt.error_json = run.error_json or {}
    elif run.status in {"failed", "timed_out", "blocked", "cancelled"}:
        step.status = "failed" if run.status in {"failed", "timed_out"} else run.status
        step.error_json = run.error_json or {"terminal_reason": run.terminal_reason}
        step.completed_at = run.completed_at or datetime.now(timezone.utc)
        attempt.status = "timed_out" if run.status == "timed_out" else "failed"
        attempt.error_json = step.error_json
        attempt.completed_at = step.completed_at
    elif run.status in {"queued", "running", "retry_scheduled"}:
        step.status = "running"
        attempt.status = "running"
        wait_until = (
            run.next_attempt_at
            or run.lease_expires_at
            or datetime.now(timezone.utc)
        )
        attempt.lease_expires_at = wait_until + timedelta(
            seconds=run.timeout_seconds + 10
        )
    else:
        step.status = "running"
        attempt.status = "running"
    attempt.lease_owner = None if attempt.status != "running" else attempt.lease_owner
    attempt.lease_expires_at = None if attempt.status != "running" else attempt.lease_expires_at


def _execute_research_step(
    session: Session,
    task: ConversationTaskRun,
    step: ConversationTaskStep,
    steps: list[ConversationTaskStep],
) -> None:
    _execute_research_batch(session, task, [step], steps)


def _execute_research_batch(
    session: Session,
    task: ConversationTaskRun,
    batch: list[ConversationTaskStep],
    steps: list[ConversationTaskStep],
) -> None:
    """Run at most two independent read-only specialists concurrently."""
    jobs: list[tuple[uuid.UUID, uuid.UUID, str, str, float]] = []
    for step in batch[:2]:
        step.attempt_count += 1
        now = datetime.now(timezone.utc)
        step.status = "running"
        step.started_at = step.started_at or now
        attempt = ConversationTaskStepAttempt(
            task_step_id=step.id,
            attempt_number=step.attempt_count,
            executor_type="research",
            status="running",
            trace_run_id=task.trace_run_id,
            input_summary=_bounded_json(step.input_json),
            lease_owner=f"task:{task.id}",
            lease_expires_at=now + timedelta(seconds=step.timeout_seconds + 10),
            started_at=now,
        )
        session.add(attempt)
        session.flush()
        system, prompt = _research_prompt(task, step, steps)
        jobs.append((step.id, attempt.id, system, prompt, time.monotonic()))
    # The in-flight truth must survive a process restart before Provider I/O.
    session.commit()
    results = _run_research_jobs([
        (system, prompt) for _, _, system, prompt, _ in jobs
    ])
    session.refresh(task, with_for_update=True)
    for (step_id, attempt_id, _, _, started), result in zip(jobs, results):
        step = session.get(ConversationTaskStep, step_id)
        attempt = session.get(ConversationTaskStepAttempt, attempt_id)
        if step is None or attempt is None or attempt.status != "running":
            continue
        if task.status in {"cancelled", "paused"} or task.cancellation_requested:
            attempt.status = "cancelled"
            attempt.completed_at = datetime.now(timezone.utc)
            attempt.lease_owner = None
            attempt.lease_expires_at = None
            if step.status == "running":
                step.status = "cancelled" if task.status == "cancelled" else "pending"
            continue
        _apply_research_result(
            task,
            step,
            attempt,
            result,
            elapsed_ms=int((time.monotonic() - started) * 1000),
        )


def _research_prompt(
    task: ConversationTaskRun,
    step: ConversationTaskStep,
    steps: list[ConversationTaskStep],
) -> tuple[str, str]:
    dependency_evidence = [
        {
            "step_order": item.step_order,
            "title": item.title,
            "observation": _safe_observation(item.output_json),
            "evidence_refs": (item.evidence_refs or [])[:8],
        }
        for item in steps
        if item.step_order in set(step.dependencies_json or [])
    ]
    system = """You are an internal read-only Research specialist for one Echora TaskStep.
Use only the supplied scoped goal, step instruction, and dependency observations.
Do not call tools, browse, write data, speak as a Companion, access memory, infer another Companion's state, or expose reasoning_content.
Return one JSON object: {"summary":string,"findings":string[],"evidence_refs":object[],"limitations":string[]}."""
    prompt = json.dumps({
        "goal": task.goal[:1200],
        "step": step.title[:500],
        "instruction": _safe_observation(step.input_json),
        "dependencies": dependency_evidence,
    }, ensure_ascii=False, default=str)
    return system, prompt


def _call_research_provider(system: str, prompt: str) -> dict[str, Any]:
    try:
        raw = OpenAICompatibleProvider().generate(
            system, prompt, context={"temperature": 0.0, "max_tokens": 1000}
        )
        output = _parse_specialist_output(raw.get("content"))
        if not output.get("summary"):
            raise ValueError("empty specialist summary")
        return {"ok": True, "raw": raw, "output": output}
    except (LLMProviderError, ValueError, TypeError, KeyError) as exc:
        return {
            "ok": False,
            "failure_type": type(exc).__name__,
        }


def _run_research_jobs(
    jobs: list[tuple[str, str]],
) -> list[dict[str, Any]]:
    bounded = jobs[:2]
    if not bounded:
        return []
    with ThreadPoolExecutor(max_workers=len(bounded)) as pool:
        futures = [
            pool.submit(_call_research_provider, system, prompt)
            for system, prompt in bounded
        ]
        return [future.result() for future in futures]


def _apply_research_result(
    task: ConversationTaskRun,
    step: ConversationTaskStep,
    attempt: ConversationTaskStepAttempt,
    result: dict[str, Any],
    *,
    elapsed_ms: int,
) -> None:
    now = datetime.now(timezone.utc)
    if result.get("ok"):
        raw = result["raw"]
        output = result["output"]
        usage = raw.get("usage") if isinstance(raw.get("usage"), dict) else {}
        task.token_count += int(usage.get("total_tokens") or 0)
        if task.token_count <= task.max_tokens:
            step.status = "succeeded"
            step.output_json = output
            step.evidence_refs = output.get("evidence_refs") or []
            attempt.status = "succeeded"
            attempt.provider_name = raw.get("provider")
            attempt.model_name = raw.get("model")
            attempt.token_usage_json = usage
            attempt.observation_json = output
            attempt.verification_json = {
                "status": "accepted",
                "summary_present": True,
            }
        else:
            result = {"ok": False, "failure_type": "TaskTokenBudgetExceeded"}
    if not result.get("ok"):
        step.status = "failed"
        step.error_json = {
            "code": "TASK_RESEARCH_FAILED",
            "failure_type": result.get("failure_type") or "UnknownProviderFailure",
        }
        attempt.status = "failed"
        attempt.error_json = step.error_json
    step.completed_at = now
    attempt.elapsed_ms = elapsed_ms
    attempt.completed_at = now
    attempt.lease_owner = None
    attempt.lease_expires_at = None


def _execute_verify_step(
    session: Session,
    task: ConversationTaskRun,
    step: ConversationTaskStep,
    steps: list[ConversationTaskStep],
) -> None:
    step.attempt_count += 1
    now = datetime.now(timezone.utc)
    dependencies = [
        item for item in steps if item.step_order in set(step.dependencies_json or [])
    ]
    failures = [
        {
            "step_order": item.step_order,
            "status": item.status,
            "reason": (item.error_json or {}).get("code"),
        }
        for item in dependencies
        if item.status != "succeeded" or not (item.output_json or item.evidence_refs)
    ]
    accepted = bool(dependencies) and not failures
    verification = {
        "status": "accepted" if accepted else "rejected",
        "criteria": step.acceptance_criteria_json or [],
        "dependency_count": len(dependencies),
        "failures": failures,
    }
    attempt = ConversationTaskStepAttempt(
        task_step_id=step.id,
        attempt_number=step.attempt_count,
        executor_type="verify",
        status="succeeded" if accepted else "failed",
        trace_run_id=task.trace_run_id,
        input_summary="Verify structured dependency evidence.",
        verification_json=verification,
        observation_json={"dependency_step_orders": [item.step_order for item in dependencies]},
        error_json={} if accepted else {"code": "TASK_VERIFICATION_REJECTED"},
        started_at=now,
        completed_at=now,
        elapsed_ms=0,
    )
    session.add(attempt)
    step.status = "succeeded" if accepted else "failed"
    step.output_json = verification
    step.error_json = attempt.error_json
    step.evidence_refs = [
        ref
        for item in dependencies
        for ref in (item.evidence_refs or [])[:8]
    ][:30]
    step.started_at = step.started_at or now
    step.completed_at = now


def _mark_ready_steps(steps: list[ConversationTaskStep]) -> None:
    succeeded = {step.step_order for step in steps if step.status == "succeeded"}
    terminal_failure = {
        step.step_order
        for step in steps
        if step.status in {"failed", "blocked", "cancelled"}
    }
    for step in steps:
        if step.status != "pending":
            continue
        dependencies = set(step.dependencies_json or [])
        if dependencies & terminal_failure:
            step.status = "blocked"
            step.error_json = {"code": "TASK_DEPENDENCY_FAILED"}
        elif dependencies.issubset(succeeded):
            step.status = "ready"


def _pause_task(task: ConversationTaskRun, reason: str) -> None:
    if task.status in TERMINAL_TASK_STATUSES:
        return
    task.status = "paused"
    task.paused_at = datetime.now(timezone.utc)
    task.stop_reason = reason
    task.revision += 1


def _resume_task(task: ConversationTaskRun) -> None:
    if task.status != "paused":
        return
    task.status = "ready"
    task.paused_at = None
    task.stop_reason = None
    task.revision += 1


def _cancel_task(
    session: Session, task: ConversationTaskRun, reason: str
) -> None:
    if task.status in TERMINAL_TASK_STATUSES:
        return
    task.cancellation_requested = True
    task.status = "cancelled"
    task.stop_reason = reason
    task.completed_at = datetime.now(timezone.utc)
    task.revision += 1
    for step in _steps(session, task.id):
        if step.status not in TERMINAL_STEP_STATUSES:
            attempt = session.execute(
                select(ConversationTaskStepAttempt)
                .where(ConversationTaskStepAttempt.task_step_id == step.id)
                .order_by(ConversationTaskStepAttempt.attempt_number.desc())
                .limit(1)
            ).scalar_one_or_none()
            if attempt and attempt.tool_run_id:
                run = session.get(ToolRun, attempt.tool_run_id)
                if run and run.status not in {
                    "succeeded", "failed", "cancelled", "blocked", "timed_out"
                }:
                    request_task_tool_cancellation(
                        session,
                        run,
                        reason=reason,
                    )
            step.status = "cancelled"
            step.completed_at = task.completed_at


def _project_to_state(
    session: Session,
    state: ConversationAgentState,
    task: ConversationTaskRun,
) -> None:
    projection = _task_projection(session, task)
    state["task_run"] = projection
    state["task_context"] = _safe_task_context(projection)
    _trace(state, "completed", "task_projected", projection)


def _task_projection(
    session: Session, task: ConversationTaskRun
) -> dict[str, Any]:
    steps = _steps(session, task.id)
    return {
        "id": str(task.id),
        "user_id": str(task.user_id),
        "companion_id": str(task.companion_id),
        "conversation_id": str(task.conversation_id),
        "source_message_id": str(task.source_message_id),
        "goal": task.goal,
        "status": task.status,
        "acceptance_state": task.acceptance_state,
        "plan_version": task.plan_version,
        "revision": task.revision,
        "current_step_order": task.current_step_order,
        "budgets": {
            "max_steps": task.max_steps,
            "max_replans": task.max_replans,
            "replan_count": task.replan_count,
            "max_tool_runs": task.max_tool_runs,
            "tool_run_count": task.tool_run_count,
            "max_tokens": task.max_tokens,
            "token_count": task.token_count,
        },
        "stop_reason": task.stop_reason,
        "steps": [
            {
                "id": str(step.id),
                "order": step.step_order,
                "title": step.title,
                "executor_type": step.executor_type,
                "capability": step.capability,
                "risk_level": step.risk_level,
                "status": step.status,
                "dependencies": step.dependencies_json or [],
                "confirmation_required": step.confirmation_required,
                "attempt_count": step.attempt_count,
                "acceptance_criteria": step.acceptance_criteria_json or [],
                "output": _safe_observation(step.output_json),
                "error": _safe_observation(step.error_json),
                "evidence_refs": (step.evidence_refs or [])[:30],
            }
            for step in steps
        ],
        "created_at": task.created_at.isoformat() if task.created_at else None,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "reasoning_content_persisted": False,
    }


def _safe_task_context(projection: dict[str, Any]) -> dict[str, Any]:
    steps = projection.get("steps") or []
    return {
        "contract_version": "conversation-task-context.v1",
        "task_run_id": projection.get("id"),
        "goal": str(projection.get("goal") or "")[:1200],
        "status": projection.get("status"),
        "acceptance_state": projection.get("acceptance_state"),
        "current_step_order": projection.get("current_step_order"),
        "steps": [
            {
                "order": item.get("order"),
                "title": str(item.get("title") or "")[:300],
                "executor_type": item.get("executor_type"),
                "capability": item.get("capability"),
                "status": item.get("status"),
                "observation": _safe_observation(item.get("output")),
                "evidence_refs": (item.get("evidence_refs") or [])[:8],
                "error": item.get("error") or {},
            }
            for item in steps[:6]
        ],
        "budgets": projection.get("budgets") or {},
        "stop_reason": projection.get("stop_reason"),
        "reasoning_content_persisted": False,
    }


def _steps(
    session: Session, task_run_id: uuid.UUID
) -> list[ConversationTaskStep]:
    return list(session.execute(
        select(ConversationTaskStep)
        .where(ConversationTaskStep.task_run_id == task_run_id)
        .order_by(ConversationTaskStep.step_order)
    ).scalars().all())


def _scope_context(
    session: Session,
    state: ConversationAgentState,
) -> dict[str, uuid.UUID]:
    context = {
        "user_id": uuid.UUID(state["user_id"]),
        "companion_id": uuid.UUID(state["companion_id"]),
        "conversation_id": uuid.UUID(state["conversation_id"]),
    }
    conversation = session.get(Conversation, context["conversation_id"])
    if (
        conversation is None
        or conversation.user_id != context["user_id"]
        or conversation.companion_id != context["companion_id"]
        or conversation.status != "active"
        or conversation.deleted_at is not None
        or is_companion_room_conversation(conversation)
    ):
        raise ConversationTurnError(
            "TASK_SCOPE_MISMATCH",
            "Task planning requires the active same-Companion Conversation.",
        )
    return context


def _check_scope(
    task: ConversationTaskRun,
    state: ConversationAgentState,
) -> None:
    if (
        str(task.user_id) != state.get("user_id")
        or str(task.companion_id) != state.get("companion_id")
        or str(task.conversation_id) != state.get("conversation_id")
    ):
        raise ConversationTurnError(
            "TASK_SCOPE_MISMATCH", "TaskRun scope does not match this turn."
        )


def _check_hard_stop(
    session: Session,
    context: dict[str, uuid.UUID],
) -> None:
    active = _hard_stop_active(session, context)
    if active:
        raise ConversationTurnError(
            "TASK_HARD_STOP_ACTIVE",
            "Companion hard stop is active; task execution is blocked.",
        )


def _hard_stop_active(
    session: Session,
    context: dict[str, uuid.UUID],
) -> bool:
    active = session.execute(
        select(ScopedHardStopEvent)
        .where(
            ScopedHardStopEvent.user_id == context["user_id"],
            ScopedHardStopEvent.companion_id == context["companion_id"],
            ScopedHardStopEvent.hard_stop_status == "active",
        )
        .limit(1)
    ).scalar_one_or_none()
    return active is not None


def _task_action(text: str) -> str | None:
    if _PAUSE.fullmatch(text):
        return "pause"
    if _RESUME.fullmatch(text):
        return "resume"
    if _CANCEL.fullmatch(text):
        return "cancel"
    return None


def _safe_observation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: dict[str, Any] = {}
    for key, item in list(value.items())[:30]:
        normalized_key = str(key)
        lowered = normalized_key.lower()
        if any(
            marker in lowered
            for marker in {
                "reasoning_content", "credential", "access_token", "refresh_token",
                "api_key", "secret", "raw_html", "system_prompt",
            }
        ):
            continue
        if isinstance(item, str):
            safe[normalized_key] = item[:2000]
        elif isinstance(item, (int, float, bool)) or item is None:
            safe[normalized_key] = item
        elif isinstance(item, list):
            projected: list[Any] = []
            for part in item[:12]:
                if isinstance(part, str):
                    projected.append(part[:500])
                elif isinstance(part, (int, float, bool)) or part is None:
                    projected.append(part)
                elif isinstance(part, dict):
                    projected.append(_safe_observation(part))
            safe[normalized_key] = projected
        elif isinstance(item, dict):
            safe[normalized_key] = _safe_observation(
                dict(list(item.items())[:12])
            )
    return safe


def _parse_specialist_output(content: Any) -> dict[str, Any]:
    text = str(content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    start = text.find("{")
    if start < 0:
        raise ValueError("missing specialist JSON")
    value, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(value, dict):
        raise ValueError("specialist result is not an object")
    return {
        "summary": str(value.get("summary") or "")[:3000],
        "findings": [
            str(item)[:500]
            for item in value.get("findings", [])
            if isinstance(item, str)
        ][:12],
        "evidence_refs": [
            item for item in value.get("evidence_refs", []) if isinstance(item, dict)
        ][:20],
        "limitations": [
            str(item)[:500]
            for item in value.get("limitations", [])
            if isinstance(item, str)
        ][:8],
    }


def _plan_snapshot(plan: TaskPlan) -> dict[str, Any]:
    return {
        "goal": plan.goal,
        "steps": [
            {
                "order": step.order,
                "title": step.title,
                "executor_type": step.executor_type,
                "capability": step.capability,
                "arguments": step.arguments,
                "dependencies": step.dependencies,
                "risk_level": step.risk_level,
                "acceptance_criteria": step.acceptance_criteria,
                "confirmation_required": step.confirmation_required,
            }
            for step in plan.steps
        ],
    }


def _bounded_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)[:2000]


def _trace(
    state: ConversationAgentState,
    status: str,
    reason: str,
    task: dict[str, Any] | None = None,
) -> None:
    state.setdefault("trace_steps", []).append({
        "step": "conversation_task_runtime",
        "order": 44,
        "status": status,
        "reason": reason,
        "task_run_id": (task or {}).get("id"),
        "task_status": (task or {}).get("status"),
        "plan_version": (task or {}).get("plan_version"),
        "budgets": (task or {}).get("budgets") or {},
        "reasoning_content_persisted": False,
    })
