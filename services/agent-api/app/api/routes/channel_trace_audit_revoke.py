"""Channel trace, audit, and revoke API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import channel_trace_audit_revoke_service

router = APIRouter(tags=["Channel Safety"])


@router.get("/channel-trace-events")
def list_channel_trace_events(
    channel_binding_id: str | None = Query(None),
    event_type: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = channel_trace_audit_revoke_service.list_trace_events(
        channel_binding_id=uuid.UUID(channel_binding_id) if channel_binding_id else None,
        event_type=event_type,
        status=status,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/channel-audit-logs")
def list_channel_audit_logs(
    channel_binding_id: str | None = Query(None),
    audit_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = channel_trace_audit_revoke_service.list_audit_logs(
        channel_binding_id=uuid.UUID(channel_binding_id) if channel_binding_id else None,
        audit_type=audit_type,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/channel-revoke-events")
def list_channel_revoke_events(
    channel_binding_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = channel_trace_audit_revoke_service.list_revoke_events(
        channel_binding_id=uuid.UUID(channel_binding_id) if channel_binding_id else None,
        status=status,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/channel-revokes/{channel_binding_id}/apply")
def apply_channel_revoke(channel_binding_id: str, body: dict | None = None):
    data = channel_trace_audit_revoke_service.apply_revoke(uuid.UUID(channel_binding_id), body or {})
    if not data:
        return err("CHANNEL_REVOKE_FAILED", "Unable to apply channel revoke")
    return ok(data)
