"""Channel message inbound/outbound API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import channel_message_service

router = APIRouter(tags=["Channel Messages"])


@router.get("/channel-message-events")
def list_channel_message_events(
    channel_binding_id: str | None = Query(None),
    direction: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = channel_message_service.list_message_events(
        channel_binding_id=uuid.UUID(channel_binding_id) if channel_binding_id else None,
        direction=direction,
        status=status,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/channel-message-events/inbound")
def ingest_channel_inbound_message(body: dict):
    data = channel_message_service.ingest_inbound(body or {})
    if not data:
        return err("CHANNEL_INBOUND_INGEST_FAILED", "Unable to ingest inbound channel message")
    return ok(data)


@router.get("/channel-delivery-events")
def list_channel_delivery_events(
    channel_binding_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = channel_message_service.list_delivery_events(
        channel_binding_id=uuid.UUID(channel_binding_id) if channel_binding_id else None,
        status=status,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/channel-delivery-events/outbound")
def queue_channel_outbound_delivery(body: dict):
    data = channel_message_service.queue_outbound(body or {})
    if not data:
        return err("CHANNEL_OUTBOUND_QUEUE_FAILED", "Unable to queue outbound channel delivery")
    return ok(data)
