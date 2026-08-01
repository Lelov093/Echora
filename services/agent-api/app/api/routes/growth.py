"""Growth Candidate & Growth Record API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok, err
from app.schemas.growth_control import (
    GrowthCandidateEditRequest,
    GrowthSuggestionPolicyUpdate,
)
from app.services import growth_control_service, growth_service

router = APIRouter(tags=["Growth"])


def _get_seed_ids():
    from app.db.models import User, Companion
    s = growth_service.get_session()
    u = s.query(User).first()
    c = s.query(Companion).first()
    s.close()
    return (u.id if u else uuid.uuid4(), c.id if c else uuid.uuid4())


# ── Growth Candidates ────────────────────────────────────────────────

@router.get("/companions/{companion_id}/growth-policy")
def get_growth_policy(companion_id: str):
    try:
        return ok(growth_control_service.get_policy(uuid.UUID(companion_id)))
    except growth_control_service.GrowthControlError as exc:
        return err(exc.code, exc.message, exc.details)


@router.put("/companions/{companion_id}/growth-policy")
def update_growth_policy(companion_id: str, body: GrowthSuggestionPolicyUpdate):
    try:
        result = growth_control_service.update_policy(
            uuid.UUID(companion_id),
            suggestions_enabled=body.suggestions_enabled,
            paused_types=list(body.paused_types),
            expected_updated_at=body.expected_updated_at,
        )
    except growth_control_service.GrowthControlError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(result)

@router.get("/growth-candidates")
def list_growth_candidates(companion_id: str | None = Query(None), status: str | None = Query(None),
                           page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    result = growth_service.list_growth_candidates(
        uuid.UUID(companion_id) if companion_id else None, status, page, page_size,
    )
    items = [growth_service._gc_dict(c) for c in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.get("/growth-candidates/{candidate_id}")
def get_growth_candidate(candidate_id: str):
    c = growth_service.get_growth_candidate(uuid.UUID(candidate_id))
    if not c:
        return err("GROWTH_CANDIDATE_NOT_FOUND", "Growth candidate not found")
    return ok(growth_service._gc_dict(c))


@router.post("/growth-candidates/{candidate_id}/commit")
def commit_growth_candidate(candidate_id: str, body: dict | None = None):
    candidate = growth_service.get_growth_candidate(uuid.UUID(candidate_id))
    if not candidate:
        return err("GROWTH_CANDIDATE_NOT_FOUND", "Growth candidate not found")
    apply = (body or {}).get("apply_to_companion_profile", True)
    result = growth_service.commit_growth_candidate(
        uuid.UUID(candidate_id),
        candidate.user_id,
        candidate.companion_id,
        apply,
    )
    if not result:
        return err("INVALID_STATE_TRANSITION", "Cannot commit this candidate")
    return ok(result)


@router.post("/growth-candidates/{candidate_id}/reject")
def reject_growth_candidate(candidate_id: str, body: dict | None = None):
    reason = (body or {}).get("reason")
    c = growth_service.reject_growth_candidate(uuid.UUID(candidate_id), reason)
    if not c:
        return err("GROWTH_CANDIDATE_NOT_FOUND", "Growth candidate not found")
    return ok(growth_service._gc_dict(c))


@router.patch("/growth-candidates/{candidate_id}")
def edit_growth_candidate(candidate_id: str, companion_id: str, body: GrowthCandidateEditRequest):
    try:
        candidate = growth_service.edit_growth_candidate(
            uuid.UUID(candidate_id),
            uuid.UUID(companion_id),
            content=body.content,
            reason=body.reason,
        )
    except growth_service.GrowthMutationError as exc:
        return err(exc.code, exc.message, exc.details)
    if candidate is None:
        return err("GROWTH_CANDIDATE_NOT_FOUND", "Growth candidate not found")
    return ok(growth_service._gc_dict(candidate))


# ── Growth Records ───────────────────────────────────────────────────

@router.get("/growth-records")
def list_growth_records(companion_id: str | None = Query(None),
                        page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    result = growth_service.list_growth_records(
        uuid.UUID(companion_id) if companion_id else None, page, page_size,
    )
    items = [growth_service._gr_dict(r) for r in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.get("/growth-records/{record_id}")
def get_growth_record(record_id: str):
    r = growth_service.get_growth_record(uuid.UUID(record_id))
    if not r:
        return err("GROWTH_CANDIDATE_NOT_FOUND", "Growth record not found")
    return ok(growth_service._gr_dict(r))


@router.post("/growth-records/{record_id}/revert")
def revert_growth_record(record_id: str, body: dict | None = None):
    reason = (body or {}).get("reason")
    r = growth_service.revert_growth_record(uuid.UUID(record_id), reason)
    if not r:
        return err("GROWTH_CANDIDATE_NOT_FOUND", "Growth record not found")
    return ok(growth_service._gr_dict(r))
