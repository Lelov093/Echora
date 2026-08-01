"""Cross-channel continuity API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import channel_continuity_service

router = APIRouter(tags=["Channel Continuity"])


@router.get("/channel-continuity/handoffs")
def list_channel_handoffs(
    channel_binding_id: str | None = Query(None),
    companion_id: str | None = Query(None),
    direction: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = channel_continuity_service.list_handoffs(
        channel_binding_id=uuid.UUID(channel_binding_id) if channel_binding_id else None,
        companion_id=uuid.UUID(companion_id) if companion_id else None,
        direction=direction,
        status=status,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/channel-continuity/web-to-channel")
def create_web_to_channel_handoff(body: dict):
    data = channel_continuity_service.create_web_to_channel_handoff(body or {})
    if not data:
        return err("CHANNEL_CONTINUITY_HANDOFF_FAILED", "Unable to create web-to-channel handoff")
    return ok(data)


@router.post("/channel-continuity/channel-to-web")
def create_channel_to_web_handoff(body: dict):
    data = channel_continuity_service.create_channel_to_web_handoff(body or {})
    if not data:
        return err("CHANNEL_CONTINUITY_HANDOFF_FAILED", "Unable to create channel-to-web handoff")
    return ok(data)
