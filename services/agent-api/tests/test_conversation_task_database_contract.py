"""Real PostgreSQL contract check for the durable task truth."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import (
    Conversation,
    ConversationTaskPlanRevision,
    ConversationTaskRun,
    ConversationTaskStep,
    ConversationTaskStepAttempt,
    Message,
    ToolResource,
    ToolRun,
)
from app.services import conversation_task_runtime_service as runtime
from app.services.conversation_service import (
    ConversationTurnError,
    _get_engine,
    get_session,
)
from app.tasks.planning import ReplanDecision


def test_task_truth_constraints_projection_and_rollback() -> None:
    with get_session() as lookup:
        scope = lookup.execute(
            select(Conversation, Message)
            .join(Message, Message.conversation_id == Conversation.id)
            .where(
                Conversation.status == "active",
                Conversation.deleted_at.is_(None),
                Message.deleted_at.is_(None),
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        ).first()
    assert scope is not None, "Task database contract requires one active Conversation"
    conversation, message = scope
    task_id = uuid.uuid4()
    step_id = uuid.uuid4()

    connection = _get_engine().connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        task = ConversationTaskRun(
            id=task_id,
            user_id=conversation.user_id,
            companion_id=conversation.companion_id,
            conversation_id=conversation.id,
            source_message_id=message.id,
            goal="Rollback-safe task contract",
            status="running",
            acceptance_state="pending",
            idempotency_key=f"task-contract-{task_id}",
        )
        step = ConversationTaskStep(
            id=step_id,
            task_run_id=task_id,
            step_order=1,
            title="Read-only contract step",
            executor_type="research",
            risk_level="low",
            status="running",
            dependencies_json=[],
            input_json={"instruction": "contract"},
            acceptance_criteria_json=["evidence exists"],
        )
        session.add_all([task, step])
        session.flush()
        session.add_all([
            ConversationTaskStepAttempt(
                task_step_id=step_id,
                attempt_number=1,
                executor_type="research",
                status="running",
                lease_owner="task-contract",
            ),
            ConversationTaskPlanRevision(
                task_run_id=task_id,
                version=1,
                trigger="initial_user_goal",
                goal=task.goal,
                plan_json={"steps": [{"order": 1}]},
                changes_json={"created": True},
                created_by="planner",
                source_message_id=message.id,
            ),
        ])
        session.flush()

        projection = runtime._task_projection(session, task)
        assert projection["companion_id"] == str(conversation.companion_id)
        assert projection["conversation_id"] == str(conversation.id)
        assert projection["steps"][0]["status"] == "running"
        assert projection["reasoning_content_persisted"] is False

        with pytest.raises(IntegrityError):
            with session.begin_nested():
                session.add(ConversationTaskStep(
                    task_run_id=task_id,
                    step_order=2,
                    title="Invalid status",
                    executor_type="verify",
                    risk_level="low",
                    status="invented_terminal",
                ))
                session.flush()
        session.commit()
    finally:
        session.close()
        outer.rollback()
        connection.close()

    with get_session() as verification:
        assert verification.get(ConversationTaskRun, task_id) is None


def test_replan_appends_revision_and_does_not_reset_success(monkeypatch) -> None:
    with get_session() as lookup:
        scope = lookup.execute(
            select(Conversation, Message)
            .join(Message, Message.conversation_id == Conversation.id)
            .where(
                Conversation.status == "active",
                Conversation.deleted_at.is_(None),
                Message.deleted_at.is_(None),
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        ).first()
    assert scope is not None
    conversation, message = scope
    task_id = uuid.uuid4()
    first_step_id = uuid.uuid4()
    failed_step_id = uuid.uuid4()
    monkeypatch.setattr(
        runtime,
        "replan_step",
        lambda **_kwargs: ReplanDecision(
            action="retry",
            rationale="corrected structured arguments",
            arguments={"location": "北京", "date": "2026-07-29"},
            provider_name="test-provider",
            model_name="test-model",
            token_usage={"total_tokens": 9},
        ),
    )

    connection = _get_engine().connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        task = ConversationTaskRun(
            id=task_id,
            user_id=conversation.user_id,
            companion_id=conversation.companion_id,
            conversation_id=conversation.id,
            source_message_id=message.id,
            goal="查询两个地点并验证",
            status="blocked",
            acceptance_state="rejected",
            idempotency_key=f"task-replan-{task_id}",
        )
        succeeded = ConversationTaskStep(
            id=first_step_id,
            task_run_id=task_id,
            step_order=1,
            title="Completed weather",
            executor_type="tool",
            capability="weather",
            status="succeeded",
            dependencies_json=[],
            input_json={"location": "上海", "date": "2026-07-29"},
            output_json={"location": "上海"},
            evidence_refs=[{"type": "tool_run", "id": "completed"}],
        )
        failed = ConversationTaskStep(
            id=failed_step_id,
            task_run_id=task_id,
            step_order=2,
            title="Failed weather",
            executor_type="tool",
            capability="weather",
            status="failed",
            dependencies_json=[],
            input_json={"location": "模糊地点", "date": "2026-07-29"},
            error_json={"code": "WEATHER_LOCATION_NOT_FOUND"},
            attempt_count=1,
        )
        session.add_all([task, succeeded, failed])
        session.flush()
        session.add(
            ConversationTaskPlanRevision(
                task_run_id=task_id,
                version=1,
                trigger="initial_user_goal",
                goal=task.goal,
                plan_json={"steps": [{"order": 1}, {"order": 2}]},
                changes_json={"created": True},
                created_by="planner",
                source_message_id=message.id,
            )
        )
        session.flush()

        repaired = runtime._attempt_replan(
            session,
            task,
            trigger="structured_step_failure",
            failed_step=failed,
        )
        session.flush()

        assert repaired is True
        assert task.plan_version == 2
        assert task.replan_count == 1
        assert task.status == "ready"
        assert succeeded.status == "succeeded"
        assert succeeded.evidence_refs == [{"type": "tool_run", "id": "completed"}]
        assert failed.status == "ready"
        assert failed.input_json["location"] == "北京"
        revisions = session.execute(
            select(ConversationTaskPlanRevision)
            .where(ConversationTaskPlanRevision.task_run_id == task_id)
            .order_by(ConversationTaskPlanRevision.version)
        ).scalars().all()
        assert [item.version for item in revisions] == [1, 2]
        assert revisions[-1].changes_json["completed_steps_reused"] == [1]
    finally:
        session.close()
        outer.rollback()
        connection.close()


def test_paused_task_blocks_confirmation_and_cancel_never_creates_side_effect() -> None:
    with get_session() as lookup:
        scope = lookup.execute(
            select(Conversation, Message)
            .join(Message, Message.conversation_id == Conversation.id)
            .where(
                Conversation.status == "active",
                Conversation.deleted_at.is_(None),
                Message.deleted_at.is_(None),
            )
            .order_by(Message.created_at.desc())
            .limit(1)
        ).first()
    assert scope is not None
    conversation, message = scope
    task_id = uuid.uuid4()
    step_id = uuid.uuid4()
    run_id = uuid.uuid4()

    connection = _get_engine().connect()
    outer = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        task = ConversationTaskRun(
            id=task_id,
            user_id=conversation.user_id,
            companion_id=conversation.companion_id,
            conversation_id=conversation.id,
            source_message_id=message.id,
            goal="创建一个需要确认的提醒",
            status="awaiting_approval",
            acceptance_state="pending",
            idempotency_key=f"task-side-effect-cancel-{task_id}",
        )
        run = ToolRun(
            id=run_id,
            user_id=conversation.user_id,
            companion_id=conversation.companion_id,
            conversation_id=conversation.id,
            request_message_id=message.id,
            requested_by="conversation_task",
            capability="reminder",
            adapter_name="local_reminder",
            adapter_version="1",
            status="awaiting_confirmation",
            risk_level="medium",
            permission_required=True,
            permission_granted=False,
            confirmation_required=True,
            confirmation_summary="创建提醒：带伞",
            idempotency_key=f"task-side-effect-tool-{run_id}",
            input_schema_version="bounded-tools.v1",
            output_schema_version="bounded-tools.v1",
            input_json={
                "title": "带伞",
                "due_at": "2026-07-29T08:00:00+08:00",
                "timezone": "Asia/Shanghai",
            },
        )
        step = ConversationTaskStep(
            id=step_id,
            task_run_id=task_id,
            step_order=1,
            title="创建带伞提醒",
            executor_type="tool",
            capability="reminder",
            risk_level="medium",
            status="awaiting_approval",
            dependencies_json=[],
            input_json=run.input_json,
            acceptance_criteria_json=["提醒经确认后创建"],
            confirmation_required=True,
            attempt_count=1,
        )
        attempt = ConversationTaskStepAttempt(
            task_step_id=step_id,
            attempt_number=1,
            executor_type="tool",
            status="awaiting_approval",
            tool_run_id=run_id,
        )
        session.add_all([task, run, step])
        session.flush()
        session.add(attempt)
        session.flush()

        runtime._pause_task(task, "user_paused")
        session.flush()
        assert task.status == "paused"
        with pytest.raises(ConversationTurnError) as paused:
            runtime.ensure_task_tool_confirmation_allowed(session, run.id)
        assert paused.value.code == "TASK_RUN_PAUSED"

        runtime._resume_task(task)
        session.flush()
        assert task.status == "ready"
        assert run.status == "awaiting_confirmation"

        runtime._cancel_task(session, task, "user_cancelled")
        session.flush()
        assert task.status == "cancelled"
        assert step.status == "cancelled"
        assert run.status == "cancelled"
        assert run.confirmed_at is None
        assert session.execute(
            select(ToolResource).where(ToolResource.source_tool_run_id == run.id)
        ).scalar_one_or_none() is None
    finally:
        session.close()
        outer.rollback()
        connection.close()

    with get_session() as verification:
        assert verification.get(ConversationTaskRun, task_id) is None
        assert verification.get(ToolRun, run_id) is None
