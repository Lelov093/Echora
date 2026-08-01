"""Delegated execution API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import delegated_execution_service

router = APIRouter(tags=["Delegated Execution"])


@router.get("/delegated-executions/intents")
def list_delegation_intents(
    user_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = delegated_execution_service.list_delegation_intents(
        user_id=uuid.UUID(user_id) if user_id else None,
        status=status,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/delegated-executions/intents")
def create_delegation_intent(body: dict):
    row = delegated_execution_service.create_delegation_intent(body or {})
    return ok(row) if row else err("DELEGATION_INTENT_CREATE_FAILED", "Unable to create delegation intent")


@router.get("/delegated-executions/intents/{trace_run_id}")
def get_delegation_intent(trace_run_id: str):
    row = delegated_execution_service.get_delegation_intent(uuid.UUID(trace_run_id))
    return ok(row) if row else err("DELEGATION_INTENT_NOT_FOUND", "Delegation intent not found")


@router.post("/delegated-executions/intents/{trace_run_id}/link")
def link_execution(trace_run_id: str, body: dict):
    row = delegated_execution_service.link_tool_run_or_project_task(uuid.UUID(trace_run_id), body or {})
    return ok(row) if row else err("DELEGATION_LINK_FAILED", "Unable to link delegated execution")


@router.post("/delegated-executions/intents/{trace_run_id}/inspect")
def inspect_execution(trace_run_id: str, body: dict):
    row = delegated_execution_service.inspect_execution_result(uuid.UUID(trace_run_id), body or {})
    return ok(row) if row else err("DELEGATION_INSPECT_FAILED", "Unable to inspect delegated execution")


@router.post("/delegated-executions/intents/{trace_run_id}/shared-experience")
def create_shared_experience(trace_run_id: str, body: dict):
    row = delegated_execution_service.create_shared_experience_from_result_candidate(uuid.UUID(trace_run_id), body or {})
    return ok(row) if row else err("DELEGATION_SHARED_EXPERIENCE_FAILED", "Unable to create shared experience candidate")
