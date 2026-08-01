"""Companion-scoped quality feedback API."""

import uuid

from fastapi import APIRouter

from app.schemas.common import err, ok
from app.schemas.quality_feedback import (
    QualityFeedbackRetestRequest,
    QualityFeedbackRetryRequest,
)
from app.services import quality_feedback_service


router = APIRouter(tags=["Quality Feedback"])


@router.get("/companions/{companion_id}/quality-feedback")
def get_quality_feedback_overview(companion_id: str):
    try:
        return ok(quality_feedback_service.get_quality_overview(uuid.UUID(companion_id)))
    except ValueError as exc:
        return err("QUALITY_FEEDBACK_SCOPE_MISMATCH", str(exc))


@router.post("/companions/{companion_id}/quality-feedback/traces/{trace_run_id}")
def enqueue_trace_feedback(companion_id: str, trace_run_id: str):
    try:
        run = quality_feedback_service.enqueue_trace_feedback(
            uuid.UUID(trace_run_id),
            expected_companion_id=uuid.UUID(companion_id),
            trigger_type="explicit_trace_review",
        )
    except ValueError as exc:
        return err("QUALITY_FEEDBACK_SCOPE_MISMATCH", str(exc))
    if run is None:
        return err("QUALITY_FEEDBACK_TRACE_NOT_TERMINAL", "Trace is missing or not terminal")
    return ok(run)


@router.post("/companions/{companion_id}/quality-feedback/{run_id}/retry")
def retry_quality_feedback(companion_id: str, run_id: str, body: QualityFeedbackRetryRequest):
    try:
        run = quality_feedback_service.retry_feedback_run(
            uuid.UUID(companion_id),
            uuid.UUID(run_id),
            expected_attempt_count=body.expected_attempt_count,
        )
    except ValueError as exc:
        return err("QUALITY_FEEDBACK_RETRY_REJECTED", str(exc))
    return ok(run)


@router.post("/companions/{companion_id}/quality-feedback/{run_id}/retest")
def retest_quality_feedback(companion_id: str, run_id: str, body: QualityFeedbackRetestRequest):
    try:
        run = quality_feedback_service.retest_feedback_run(
            uuid.UUID(companion_id),
            uuid.UUID(run_id),
            expected_feedback_revision=body.expected_feedback_revision,
            reason=body.reason,
        )
    except ValueError as exc:
        return err("QUALITY_FEEDBACK_RETEST_REJECTED", str(exc))
    return ok(run)
