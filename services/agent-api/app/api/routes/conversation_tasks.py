"""Scoped durable Conversation TaskRun read and control routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok
from app.services import conversation_task_runtime_service
from app.services.conversation_service import ConversationTurnError


router = APIRouter(prefix="/conversation-tasks", tags=["Conversation Tasks"])


@router.get("")
def list_conversation_tasks(
    companion_id: str = Query(...),
    conversation_id: str = Query(...),
    status: str | None = Query(None),
):
    try:
        rows = conversation_task_runtime_service.list_task_runs(
            companion_id=uuid.UUID(companion_id),
            conversation_id=uuid.UUID(conversation_id),
            status=status,
        )
    except (ValueError, ConversationTurnError) as exc:
        return _error(exc)
    return ok(rows)


@router.get("/{task_run_id}")
def get_conversation_task(
    task_run_id: str,
    companion_id: str = Query(...),
    conversation_id: str = Query(...),
):
    try:
        row = conversation_task_runtime_service.get_task_run(
            uuid.UUID(task_run_id),
            companion_id=uuid.UUID(companion_id),
            conversation_id=uuid.UUID(conversation_id),
        )
    except (ValueError, ConversationTurnError) as exc:
        return _error(exc)
    return ok(row) if row else err("TASK_RUN_NOT_FOUND", "TaskRun not found.")


@router.post("/{task_run_id}/{action}")
def control_conversation_task(
    task_run_id: str,
    action: str,
    companion_id: str = Query(...),
    conversation_id: str = Query(...),
):
    try:
        row = conversation_task_runtime_service.task_action(
            uuid.UUID(task_run_id),
            companion_id=uuid.UUID(companion_id),
            conversation_id=uuid.UUID(conversation_id),
            action=action,
        )
    except (ValueError, ConversationTurnError) as exc:
        return _error(exc)
    return ok(row) if row else err("TASK_RUN_NOT_FOUND", "TaskRun not found.")


def _error(exc: Exception) -> dict:
    if isinstance(exc, ConversationTurnError):
        return err(exc.code, exc.message, exc.details)
    return err("TASK_REQUEST_INVALID", "TaskRun request contains an invalid identifier.")
