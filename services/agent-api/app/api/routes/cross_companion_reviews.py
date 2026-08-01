"""Cross-companion memory review routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import cross_companion_review_service

router = APIRouter(tags=["Cross Companion Reviews"])


def _get_seed_user_id() -> uuid.UUID:
    from app.db.models import User

    s = cross_companion_review_service.get_session()
    u = s.query(User).first()
    s.close()
    return u.id if u else uuid.uuid4()


@router.get("/cross-companion-memory-reviews")
def list_cross_companion_memory_reviews(
    decision: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = cross_companion_review_service.list_cross_companion_memory_reviews(
        decision=decision, page=page, page_size=page_size
    )
    items = [cross_companion_review_service._cross_review_dict(item) for item in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.post("/cross-companion-memory-reviews")
def create_cross_companion_memory_review(body: dict):
    user_id = uuid.UUID(body["user_id"]) if body.get("user_id") else _get_seed_user_id()
    review = cross_companion_review_service.create_cross_companion_memory_review(user_id, body or {})
    if not review:
        return err("CROSS_COMPANION_REVIEW_CREATE_FAILED", "Unable to create cross-companion review")
    return ok(cross_companion_review_service._cross_review_dict(review))


@router.post("/cross-companion-memory-reviews/{review_id}/decision")
def decide_cross_companion_memory_review(review_id: str, body: dict):
    result = cross_companion_review_service.decide_cross_companion_memory_review(uuid.UUID(review_id), body or {})
    if not result:
        return err("CROSS_COMPANION_REVIEW_NOT_FOUND", "Cross-companion review not found")
    return ok(result)
