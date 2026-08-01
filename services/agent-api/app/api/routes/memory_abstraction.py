"""Memory Abstraction API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok, err
from app.services import memory_abstraction_service

router = APIRouter(tags=["Memory Abstraction"])


@router.post("/memory-abstraction-candidates")
def create_candidate(body: dict):
    result = memory_abstraction_service.create_candidate(body)
    return ok(result)


@router.get("/memory-abstraction-candidates")
def list_candidates(
    companion_id: str | None = Query(None),
    status: str | None = Query(None),
    abstraction_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = memory_abstraction_service.list_candidates(
        companion_id=uuid.UUID(companion_id) if companion_id else None,
        status=status,
        abstraction_type=abstraction_type,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/memory-abstraction-candidates/{candidate_id}")
def get_candidate(candidate_id: str):
    ac = memory_abstraction_service.get_candidate(uuid.UUID(candidate_id))
    if not ac:
        return err("NOT_FOUND", "Memory abstraction candidate not found")
    return ok(ac)


@router.post("/memory-abstraction-candidates/{candidate_id}/accept-as-memory")
def accept_as_memory(candidate_id: str, body: dict):
    result = memory_abstraction_service.accept_as_memory(uuid.UUID(candidate_id), body)
    if not result:
        return err("NOT_FOUND", "Memory abstraction candidate not found")
    return ok(result)


@router.post("/memory-abstraction-candidates/{candidate_id}/accept-as-growth")
def accept_as_growth(candidate_id: str, body: dict):
    result = memory_abstraction_service.accept_as_growth(uuid.UUID(candidate_id), body)
    if not result:
        return err("NOT_FOUND", "Memory abstraction candidate not found")
    return ok(result)


@router.post("/memory-abstraction-candidates/{candidate_id}/edit-accept")
def edit_accept(candidate_id: str, body: dict):
    result = memory_abstraction_service.edit_accept(uuid.UUID(candidate_id), body)
    if not result:
        return err("NOT_FOUND", "Memory abstraction candidate not found")
    return ok(result)


@router.post("/memory-abstraction-candidates/{candidate_id}/reject")
def reject_candidate(candidate_id: str, body: dict = None):
    result = memory_abstraction_service.reject_candidate(uuid.UUID(candidate_id), body or {})
    if not result:
        return err("NOT_FOUND", "Memory abstraction candidate not found")
    return ok(result)
