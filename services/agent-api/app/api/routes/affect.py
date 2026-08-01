import uuid

from fastapi import APIRouter, Query

from app.schemas.affect import AffectCorrectionRequest, AffectPreferenceUpdate
from app.schemas.common import err, ok, paginated_ok
from app.services import affect_service


router = APIRouter(tags=["Affect"])


@router.get("/companions/{companion_id}/affect")
def get_affect(companion_id: str):
    return ok(affect_service.get_affect_state(uuid.UUID(companion_id)))


@router.get("/companions/{companion_id}/affect/events")
def list_events(companion_id: str, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    result = affect_service.list_affect_events(uuid.UUID(companion_id), page, page_size)
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.patch("/companions/{companion_id}/affect/preferences")
def update_preferences(companion_id: str, payload: AffectPreferenceUpdate):
    try:
        return ok(affect_service.update_expression_preferences(uuid.UUID(companion_id), expected_revision=payload.expected_revision,
            enabled=payload.expression_enabled, intensity=payload.expression_intensity))
    except affect_service.AffectMutationError as exc:
        return err(exc.code, exc.message, exc.details)


@router.post("/companions/{companion_id}/affect/events/{event_id}/correct")
def correct_event(companion_id: str, event_id: str, payload: AffectCorrectionRequest):
    try:
        return ok(affect_service.invalidate_event(uuid.UUID(event_id), uuid.UUID(companion_id), expected_revision=payload.expected_revision, reason=payload.reason))
    except affect_service.AffectMutationError as exc:
        return err(exc.code, exc.message, exc.details)
