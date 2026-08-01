"""Growth consistency API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok
from app.services import growth_consistency_service

router = APIRouter(tags=["Growth Consistency"])


@router.get("/growth-consistency-checks")
def list_growth_consistency_checks(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    growth_candidate_id: str | None = None,
    trace_run_id: str | None = None,
):
    result = growth_consistency_service.list_growth_consistency_checks(
        page,
        page_size,
        growth_candidate_id=uuid.UUID(growth_candidate_id) if growth_candidate_id else None,
        trace_run_id=uuid.UUID(trace_run_id) if trace_run_id else None,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/growth-consistency-checks")
def create_growth_consistency_check(body: dict):
    return ok(growth_consistency_service.create_growth_consistency_check(body))
