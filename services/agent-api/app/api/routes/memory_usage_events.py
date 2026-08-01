"""Memory Usage Event API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok, err
from app.services import memory_usage_service

router = APIRouter(tags=["Memory Usage Events"])


@router.post("/memory-usage-events")
def create_memory_usage_event(body: dict):
    result = memory_usage_service.create_memory_usage_event(body)
    return ok(result)


@router.get("/memory-usage-events")
def list_memory_usage_events(
    memory_id: str | None = Query(None),
    event_type: str | None = Query(None),
    trace_run_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = memory_usage_service.list_memory_usage_events(
        memory_id=uuid.UUID(memory_id) if memory_id else None,
        event_type=event_type,
        trace_run_id=uuid.UUID(trace_run_id) if trace_run_id else None,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/memories/{memory_id}/usage-events")
def list_usage_events_for_memory(
    memory_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = memory_usage_service.list_usage_events_for_memory(
        uuid.UUID(memory_id), page=page, page_size=page_size
    )
    return paginated_ok(result["items"], page, page_size, result["total"])
