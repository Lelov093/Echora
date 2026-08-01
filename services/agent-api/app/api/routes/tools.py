"""Bounded Tool Runtime routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.schemas.tool import ToolPermissionSet, ToolPermissionUpdate, ToolRunActionRequest
from app.services import tool_runtime_service, tool_service
from app.services.conversation_service import ConversationTurnError


router = APIRouter(tags=["Tools"])


@router.get("/tool-definitions")
def list_tool_definitions(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), companion_id: str | None = None):
    result = tool_service.list_tool_definitions(page, page_size, companion_id=uuid.UUID(companion_id) if companion_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/tool-definitions/{tool_definition_id}")
def get_tool_definition(tool_definition_id: str):
    row = tool_service.get_tool_definition(uuid.UUID(tool_definition_id))
    return ok(row) if row else err("NOT_FOUND", "Tool definition not found")


@router.get("/tool-permissions")
def list_tool_permissions(companion_id: str = Query(...), page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), tool_definition_id: str | None = None):
    result = tool_service.list_tool_permissions(page, page_size, companion_id=uuid.UUID(companion_id), tool_definition_id=uuid.UUID(tool_definition_id) if tool_definition_id else None)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.patch("/tool-permissions/{permission_id}")
def update_tool_permission(permission_id: str, body: ToolPermissionUpdate):
    row = tool_service.update_tool_permission_scoped(uuid.UUID(permission_id), body.companion_id, body.model_dump(exclude={"companion_id"}, exclude_none=True))
    return ok(row) if row else err("NOT_FOUND", "Tool permission not found in this Companion scope")


@router.put("/tool-permissions/by-definition/{tool_definition_id}")
def set_tool_permission(tool_definition_id: str, body: ToolPermissionSet):
    row = tool_service.set_tool_permission_scoped(
        uuid.UUID(tool_definition_id),
        body.companion_id,
        body.policy,
        body.reason,
    )
    return ok(row) if row else err("NOT_FOUND", "Tool definition or Companion not found in this scope")


@router.get("/tool-runs")
def list_tool_runs(companion_id: str = Query(...), conversation_id: str | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), status: str | None = None):
    result = tool_service.list_tool_runs(page, page_size, companion_id=uuid.UUID(companion_id), conversation_id=uuid.UUID(conversation_id) if conversation_id else None, status=status)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/tool-runs/{tool_run_id}")
def get_tool_run(tool_run_id: str, companion_id: str = Query(...)):
    row = tool_service.get_tool_run(uuid.UUID(tool_run_id), uuid.UUID(companion_id))
    return ok(row) if row else err("NOT_FOUND", "ToolRun not found in this Companion scope")


@router.post("/tool-runs/{tool_run_id}/confirm")
def confirm_tool_run(tool_run_id: str, body: ToolRunActionRequest):
    try:
        row = tool_runtime_service.confirm_tool_run(uuid.UUID(tool_run_id), companion_id=body.companion_id, conversation_id=body.conversation_id)
    except ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(row) if row else err("NOT_FOUND", "ToolRun not found")


@router.post("/tool-runs/{tool_run_id}/cancel")
def cancel_tool_run(tool_run_id: str, body: ToolRunActionRequest):
    try:
        row = tool_runtime_service.cancel_tool_run(uuid.UUID(tool_run_id), companion_id=body.companion_id, conversation_id=body.conversation_id, reason=body.reason)
    except ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(row) if row else err("NOT_FOUND", "ToolRun not found")


@router.post("/tool-runs/{tool_run_id}/retry")
def retry_tool_run(tool_run_id: str, body: ToolRunActionRequest):
    try:
        row = tool_runtime_service.retry_tool_run(uuid.UUID(tool_run_id), companion_id=body.companion_id, conversation_id=body.conversation_id)
    except ConversationTurnError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(row) if row else err("NOT_FOUND", "ToolRun not found")


@router.post("/tool-runs/{tool_run_id}/create-bad-case")
def create_tool_run_bad_case(tool_run_id: str, body: ToolRunActionRequest):
    row = tool_service.create_tool_run_bad_case(uuid.UUID(tool_run_id), {"description": body.reason} if body.reason else None, companion_id=body.companion_id)
    return ok(row) if row else err("NOT_FOUND", "ToolRun not found in this Companion scope")


@router.get("/tool-resources")
def list_tool_resources(companion_id: str = Query(...), resource_type: str | None = None, status: str | None = None):
    return ok(tool_runtime_service.list_tool_resources(companion_id=uuid.UUID(companion_id), resource_type=resource_type, status=status))
