"""Shared memory routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import shared_memory_service

router = APIRouter(tags=["Shared Memories"])


def _get_seed_user_id() -> uuid.UUID:
    from app.db.models import User

    s = shared_memory_service.get_session()
    u = s.query(User).first()
    s.close()
    return u.id if u else uuid.uuid4()


@router.get("/shared-episodic-memories")
def list_shared_episodic_memories(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = shared_memory_service.list_shared_episodic_memories(status=status, page=page, page_size=page_size)
    items = [shared_memory_service._shared_memory_dict(item) for item in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.post("/shared-episodic-memories")
def create_shared_episodic_memory(body: dict):
    user_id = uuid.UUID(body["user_id"]) if body.get("user_id") else _get_seed_user_id()
    shared = shared_memory_service.create_shared_episodic_memory(user_id, body or {})
    return ok(shared_memory_service._shared_memory_dict(shared))


@router.get("/shared-memory-candidates")
def list_shared_memory_candidates(
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = shared_memory_service.list_shared_memory_candidates(status=status, page=page, page_size=page_size)
    items = [shared_memory_service._shared_candidate_dict(item) for item in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.post("/shared-memory-candidates")
def create_shared_memory_candidate(body: dict):
    user_id = uuid.UUID(body["user_id"]) if body.get("user_id") else _get_seed_user_id()
    candidate = shared_memory_service.create_shared_memory_candidate(user_id, body or {})
    return ok(shared_memory_service._shared_candidate_dict(candidate))


@router.post("/shared-memory-candidates/{candidate_id}/decision")
def decide_shared_memory_candidate(candidate_id: str, body: dict):
    result = shared_memory_service.decide_shared_memory_candidate(uuid.UUID(candidate_id), body or {})
    if not result:
        return err("SHARED_MEMORY_CANDIDATE_NOT_FOUND", "Shared memory candidate not found")
    if result.get("error") == "PRIVATE_TO_SHARED_REVIEW_REQUIRED":
        return err(
            "PRIVATE_TO_SHARED_REVIEW_REQUIRED",
            "private-to-shared review must be approved before promoting this candidate",
        )
    return ok(result)


@router.get("/private-to-shared-memory-reviews")
def list_private_to_shared_reviews(
    decision: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = shared_memory_service.list_private_to_shared_reviews(decision=decision, page=page, page_size=page_size)
    items = [shared_memory_service._private_to_shared_review_dict(item) for item in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.post("/private-to-shared-memory-reviews/{review_id}/decision")
def decide_private_to_shared_review(review_id: str, body: dict):
    review = shared_memory_service.decide_private_to_shared_review(uuid.UUID(review_id), body or {})
    if not review:
        return err("PRIVATE_TO_SHARED_REVIEW_NOT_FOUND", "Private-to-shared review not found")
    return ok(shared_memory_service._private_to_shared_review_dict(review))


@router.get("/shared-to-private-memory-reviews")
def list_shared_to_private_reviews(
    decision: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = shared_memory_service.list_shared_to_private_reviews(decision=decision, page=page, page_size=page_size)
    items = [shared_memory_service._shared_to_private_review_dict(item) for item in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.post("/shared-to-private-memory-reviews/{review_id}/decision")
def decide_shared_to_private_review(review_id: str, body: dict):
    result = shared_memory_service.decide_shared_to_private_review(uuid.UUID(review_id), body or {})
    if not result:
        return err("SHARED_TO_PRIVATE_REVIEW_NOT_FOUND", "Shared-to-private review not found")
    return ok(result)
