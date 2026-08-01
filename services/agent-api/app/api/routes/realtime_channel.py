"""Deferred realtime channel event and SSE contracts."""

import uuid

from fastapi import APIRouter, Header, Query
from fastapi.responses import StreamingResponse

from app.schemas.common import err, ok
from app.services import realtime_channel_service

router = APIRouter(tags=["Realtime Channel"])


@router.post("/realtime-channels/{channel_id}/events")
def publish_realtime_channel_event(channel_id: str, body: dict):
    data = realtime_channel_service.publish_channel_event(uuid.UUID(channel_id), body or {})
    if not data:
        return err(
            "REALTIME_CHANNEL_EVENT_PUBLISH_FAILED",
            "Realtime channel not found or event type is not allowed",
            {"allowed_event_types": sorted(realtime_channel_service.PUBLISHED_EVENT_TYPES)},
        )
    return ok(data)


@router.get("/realtime-channels/{channel_id}/events/recent")
def list_recent_realtime_channel_events(
    channel_id: str,
    last_event_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
):
    data = realtime_channel_service.list_recent_channel_events(
        uuid.UUID(channel_id),
        last_event_id=last_event_id,
        limit=limit,
    )
    if data is None:
        return err("REALTIME_CHANNEL_NOT_FOUND", "Realtime channel not found")
    return ok(data)


@router.get("/realtime-channels/{channel_id}/events")
def stream_realtime_channel_events(
    channel_id: str,
    last_event_id: str | None = Query(None),
    last_event_header: str | None = Header(None, alias="Last-Event-ID"),
    max_events: int = Query(50, ge=1, le=200),
):
    return StreamingResponse(
        realtime_channel_service.iter_sse_events(
            uuid.UUID(channel_id),
            last_event_id=last_event_id or last_event_header,
            max_events=max_events,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
