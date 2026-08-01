"""Channel memory boundary and review API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import channel_memory_boundary_service

router = APIRouter(tags=["Channel Memory"])


@router.get("/channel-memory-candidates")
def list_channel_memory_candidates(
    channel_binding_id: str | None = Query(None),
    companion_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = channel_memory_boundary_service.list_candidates(
        channel_binding_id=uuid.UUID(channel_binding_id) if channel_binding_id else None,
        companion_id=uuid.UUID(companion_id) if companion_id else None,
        status=status,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/channel-memory-candidates")
def create_channel_memory_candidate(body: dict):
    data = channel_memory_boundary_service.create_candidate(body or {})
    if not data:
        return err("CHANNEL_MEMORY_CANDIDATE_CREATE_FAILED", "Unable to create channel memory candidate")
    return ok(data)


@router.get("/channel-memory-candidates/{candidate_id}")
def get_channel_memory_candidate(candidate_id: str):
    data = channel_memory_boundary_service.get_candidate(uuid.UUID(candidate_id))
    if not data:
        return err("CHANNEL_MEMORY_CANDIDATE_NOT_FOUND", "Channel memory candidate not found")
    return ok(data)


@router.post("/channel-memory-candidates/{candidate_id}/approve")
def approve_channel_memory_candidate(candidate_id: str, body: dict | None = None):
    data = channel_memory_boundary_service.approve_candidate(uuid.UUID(candidate_id), body or {})
    if not data:
        return err("CHANNEL_MEMORY_CANDIDATE_NOT_FOUND", "Channel memory candidate not found")
    return ok(data)


@router.post("/channel-memory-candidates/{candidate_id}/reject")
def reject_channel_memory_candidate(candidate_id: str, body: dict | None = None):
    data = channel_memory_boundary_service.reject_candidate(uuid.UUID(candidate_id), body or {})
    if not data:
        return err("CHANNEL_MEMORY_CANDIDATE_NOT_FOUND", "Channel memory candidate not found")
    return ok(data)


@router.post("/channel-memory-candidates/{candidate_id}/redact")
def redact_channel_memory_candidate(candidate_id: str, body: dict | None = None):
    data = channel_memory_boundary_service.redact_candidate(uuid.UUID(candidate_id), body or {})
    if not data:
        return err("CHANNEL_MEMORY_CANDIDATE_NOT_FOUND", "Channel memory candidate not found")
    return ok(data)


@router.post("/channel-memory-candidates/{candidate_id}/commit-intent")
def commit_intent_channel_memory_candidate(candidate_id: str, body: dict | None = None):
    data = channel_memory_boundary_service.commit_intent(uuid.UUID(candidate_id), body or {})
    if not data:
        return err("CHANNEL_MEMORY_COMMIT_INTENT_BLOCKED", "Commit intent requires an approved review")
    return ok(data)


@router.get("/channel-memory-reviews")
def list_channel_memory_reviews(
    candidate_id: str | None = Query(None),
    decision: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = channel_memory_boundary_service.list_reviews(
        candidate_id=uuid.UUID(candidate_id) if candidate_id else None,
        decision=decision,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])
