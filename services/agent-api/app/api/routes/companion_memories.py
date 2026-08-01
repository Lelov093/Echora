"""Companion-private memory routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import paginated_ok
from app.services import companion_memory_service

router = APIRouter(prefix="/companions", tags=["Companion Memories"])


@router.get("/{companion_id}/memories")
def list_companion_memories(
    companion_id: str,
    state: str | None = Query(None),
    scope_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = companion_memory_service.list_companion_memories(
        uuid.UUID(companion_id), state=state, scope_type=scope_type, page=page, page_size=page_size
    )
    items = [companion_memory_service._memory_dict(m) for m in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])
