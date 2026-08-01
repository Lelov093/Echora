"""Review Batch API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok, err
from app.services import review_batch_service

router = APIRouter(tags=["Review Batches"])


@router.post("/review-batches")
def create_batch(body: dict):
    result = review_batch_service.create_batch(body)
    return ok(result)


@router.get("/review-batches")
def list_batches(
    companion_id: str | None = Query(None),
    batch_type: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = review_batch_service.list_batches(
        companion_id=uuid.UUID(companion_id) if companion_id else None,
        batch_type=batch_type,
        status=status,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/review-batches/{batch_id}")
def get_batch(batch_id: str):
    rb = review_batch_service.get_batch(uuid.UUID(batch_id))
    if not rb:
        return err("NOT_FOUND", "Review batch not found")
    return ok(rb)


@router.post("/review-batches/{batch_id}/apply")
def apply_batch(batch_id: str, body: dict):
    result = review_batch_service.apply_batch(uuid.UUID(batch_id), body)
    if not result:
        return err("NOT_FOUND", "Review batch not found")
    return ok(result)
