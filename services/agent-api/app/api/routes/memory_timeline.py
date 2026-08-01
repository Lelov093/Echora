"""Memory Timeline API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok, err
from app.services import memory_timeline_service

router = APIRouter(tags=["Memory Timeline"])


@router.get("/memories/timeline")
def get_memory_timeline(
    companion_id: str | None = Query(None),
    user_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    result = memory_timeline_service.get_memory_timeline(
        companion_id=uuid.UUID(companion_id) if companion_id else None,
        user_id=uuid.UUID(user_id) if user_id else None,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/memories/{memory_id}/timeline")
def get_single_memory_timeline(
    memory_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    result = memory_timeline_service.get_single_memory_timeline(
        uuid.UUID(memory_id), page=page, page_size=page_size
    )
    return paginated_ok(result["items"], page, page_size, result["total"])
