"""Feedback Event API routes."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok, err
from app.services import feedback_service

router = APIRouter(tags=["Feedback"])


@router.post("/feedback-events")
def create_feedback_event(body: dict):
    result = feedback_service.create_feedback_event(body)
    return ok(result)


@router.get("/feedback-events")
def list_feedback_events(
    companion_id: str | None = Query(None),
    target_type: str | None = Query(None),
    target_id: str | None = Query(None),
    label: str | None = Query(None),
    calibration_status: str | None = Query(None),
    feedback_source: str | None = Query(None),
    risk_level: str | None = Query(None),
    training_eligible: bool | None = Query(None),
    created_after: datetime | None = Query(None),
    created_before: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = feedback_service.list_feedback_events(
        companion_id=uuid.UUID(companion_id) if companion_id else None,
        target_type=target_type,
        target_id=uuid.UUID(target_id) if target_id else None,
        label=label,
        calibration_status=calibration_status,
        feedback_source=feedback_source,
        risk_level=risk_level,
        training_eligible=training_eligible,
        created_after=created_after,
        created_before=created_before,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/feedback-events/{feedback_event_id}")
def get_feedback_event(feedback_event_id: str):
    fe = feedback_service.get_feedback_event(uuid.UUID(feedback_event_id))
    if not fe:
        return err("NOT_FOUND", "Feedback event not found")
    return ok(fe)


@router.patch("/feedback-events/{feedback_event_id}")
def update_feedback_event(feedback_event_id: str, body: dict):
    fe = feedback_service.update_feedback_event(uuid.UUID(feedback_event_id), body)
    if not fe:
        return err("NOT_FOUND", "Feedback event not found")
    return ok(fe)


@router.post("/feedback-events/{feedback_event_id}/apply")
def apply_feedback_event(feedback_event_id: str):
    fe = feedback_service.apply_feedback_event(uuid.UUID(feedback_event_id))
    if not fe:
        return err("NOT_FOUND", "Feedback event not found")
    return ok(fe)
