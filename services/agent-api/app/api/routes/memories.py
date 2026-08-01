"""Memory API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok, err
from app.schemas.product_crud import (
    SavedMemoryCorrectionRequest,
    SavedMemoryCreateRequest,
    SavedMemoryRevisionRestoreRequest,
)
from app.services import memory_service

router = APIRouter(prefix="/memories", tags=["Memories"])


@router.get("")
def list_memories(companion_id: str = Query(...), type: str | None = Query(None),
                  state: str | None = Query(None), page: int = Query(1, ge=1),
                  page_size: int = Query(20, ge=1, le=100)):
    result = memory_service.list_memories(
        uuid.UUID(companion_id), type, state, page, page_size,
    )
    items = [memory_service._mem_dict(m) for m in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.post("")
def create_memory(body: SavedMemoryCreateRequest):
    try:
        m = memory_service.create_memory(body.model_dump())
    except memory_service.MemoryMutationError as exc:
        return err(exc.code, exc.message, exc.details)
    except ValueError as exc:
        return err("MEMORY_SCOPE_MISMATCH", str(exc))
    return ok(memory_service._mem_dict(m))


@router.get("/{memory_id}")
def get_memory(memory_id: str, companion_id: str = Query(...)):
    m = memory_service.get_memory(uuid.UUID(memory_id), uuid.UUID(companion_id))
    if not m:
        return err("MEMORY_NOT_FOUND", "Memory not found")
    return ok(memory_service._mem_dict(m))


@router.patch("/{memory_id}")
def correct_memory(
    memory_id: str,
    body: SavedMemoryCorrectionRequest,
    companion_id: str = Query(...),
):
    try:
        m = memory_service.correct_memory(
            uuid.UUID(memory_id), uuid.UUID(companion_id),
            content=body.content.strip(), summary=body.summary, reason=body.reason,
            expected_revision=body.expected_revision,
        )
    except memory_service.MemoryMutationError as exc:
        return err(exc.code, exc.message, exc.details)
    if not m:
        return err("MEMORY_NOT_FOUND", "Memory not found")
    return ok(memory_service._mem_dict(m))


@router.get("/{memory_id}/revisions")
def list_memory_revisions(memory_id: str, companion_id: str = Query(...)):
    try:
        result = memory_service.list_memory_content_revisions(
            uuid.UUID(memory_id), uuid.UUID(companion_id),
        )
    except memory_service.MemoryMutationError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(result)


@router.post("/{memory_id}/revisions/{revision_id}/restore")
def restore_memory_revision(
    memory_id: str,
    revision_id: str,
    body: SavedMemoryRevisionRestoreRequest,
    companion_id: str = Query(...),
):
    try:
        result = memory_service.restore_memory_content_revision(
            uuid.UUID(memory_id), uuid.UUID(revision_id), uuid.UUID(companion_id),
            expected_revision=body.expected_revision,
            reason=body.reason,
        )
    except memory_service.MemoryMutationError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(memory_service._mem_dict(result))


@router.delete("/{memory_id}")
def delete_memory(memory_id: str, companion_id: str = Query(...)):
    m = memory_service.delete_memory(uuid.UUID(memory_id), uuid.UUID(companion_id))
    if not m:
        return err("MEMORY_NOT_FOUND", "Memory not found")
    return ok({"id": str(m.id), "state": m.state})


@router.post("/{memory_id}/lock")
def lock_memory(memory_id: str, companion_id: str = Query(...)):
    m = memory_service.lock_memory(uuid.UUID(memory_id), uuid.UUID(companion_id))
    if not m:
        return err("MEMORY_NOT_FOUND", "Memory not found")
    return ok(memory_service._mem_dict(m))


@router.post("/{memory_id}/fade")
def fade_memory(memory_id: str, body: dict | None = None, companion_id: str = Query(...)):
    delta = (body or {}).get("strength_delta", 0.2)
    m = memory_service.fade_memory(uuid.UUID(memory_id), delta, uuid.UUID(companion_id))
    if not m:
        return err("MEMORY_NOT_FOUND", "Memory not found")
    return ok(memory_service._mem_dict(m))


@router.post("/{memory_id}/archive")
def archive_memory(memory_id: str, companion_id: str = Query(...)):
    m = memory_service.archive_memory(uuid.UUID(memory_id), uuid.UUID(companion_id))
    if not m:
        return err("MEMORY_NOT_FOUND", "Memory not found")
    return ok(memory_service._mem_dict(m))


@router.post("/{memory_id}/reactivate")
def reactivate_memory(memory_id: str, companion_id: str = Query(...)):
    m = memory_service.reactivate_memory(uuid.UUID(memory_id), uuid.UUID(companion_id))
    if not m:
        return err("MEMORY_NOT_FOUND", "Memory not found")
    return ok(memory_service._mem_dict(m))
