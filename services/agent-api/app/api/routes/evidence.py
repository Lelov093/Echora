"""Evidence sufficiency API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok
from app.services import evidence_service

router = APIRouter(tags=["Evidence"])


@router.get("/evidence-sufficiency-events")
def list_evidence_sufficiency_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    trace_run_id: str | None = None,
    target_type: str | None = None,
    target_id: str | None = None,
):
    result = evidence_service.list_evidence_events(
        page,
        page_size,
        trace_run_id=uuid.UUID(trace_run_id) if trace_run_id else None,
        target_type=target_type,
        target_id=uuid.UUID(target_id) if target_id else None,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/evidence-sufficiency-events")
def create_evidence_sufficiency_event(body: dict):
    return ok(evidence_service.create_evidence_event(body))
