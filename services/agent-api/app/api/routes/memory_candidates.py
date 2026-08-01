"""Memory Candidate API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok, err
from app.schemas.product_crud import MemoryCandidateMergeRequest
from app.services import memory_service

router = APIRouter(prefix="/memory-candidates", tags=["Memory Candidates"])


def _get_seed_ids():
    from app.db.models import User, Companion
    s = memory_service.get_session()
    u = s.query(User).first()
    c = s.query(Companion).first()
    s.close()
    return (u.id if u else uuid.uuid4(), c.id if c else uuid.uuid4())


@router.get("")
def list_memory_candidates(companion_id: str | None = Query(None), status: str | None = Query(None),
                           page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    result = memory_service.list_memory_candidates(
        uuid.UUID(companion_id) if companion_id else None, status, page, page_size,
    )
    items = [memory_service._cand_dict(c) for c in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.get("/{candidate_id}")
def get_memory_candidate(candidate_id: str):
    c = memory_service.get_memory_candidate(uuid.UUID(candidate_id))
    if not c:
        return err("MEMORY_CANDIDATE_NOT_FOUND", "Memory candidate not found")
    return ok(memory_service._cand_dict(c))


@router.post("/{candidate_id}/accept")
def accept_memory_candidate(candidate_id: str, body: dict | None = None):
    """Accept candidate content — does NOT create Memory.

    Only sets status to 'accepted'. Call commit to create a Memory record.
    """
    result = memory_service.accept_memory_candidate(uuid.UUID(candidate_id))
    if not result:
        return err("INVALID_STATE_TRANSITION", "Cannot accept this candidate (must be pending)")
    return ok(result)


@router.post("/{candidate_id}/commit")
def commit_memory_candidate(candidate_id: str, body: dict | None = None):
    """Commit an accepted candidate → creates a Memory record.

    Idempotent: if already committed, returns the existing Memory.
    Only works on candidates with status 'accepted'.
    """
    candidate = memory_service.get_memory_candidate(uuid.UUID(candidate_id))
    if not candidate:
        return err("MEMORY_CANDIDATE_NOT_FOUND", "Memory candidate not found")
    result = memory_service.commit_memory_candidate(
        uuid.UUID(candidate_id),
        candidate.user_id,
        candidate.companion_id,
    )
    if not result:
        return err("INVALID_STATE_TRANSITION", "Cannot commit this candidate (must be accepted first)")
    return ok(result)


@router.post("/{candidate_id}/edit")
def edit_memory_candidate(candidate_id: str, body: dict):
    candidate = memory_service.get_memory_candidate(uuid.UUID(candidate_id))
    if not candidate:
        return err("MEMORY_CANDIDATE_NOT_FOUND", "Memory candidate not found")
    result = memory_service.edit_memory_candidate(
        uuid.UUID(candidate_id),
        content=body.get("content"),
        summary=body.get("summary"),
        type_=body.get("type"),
        accept_after_edit=body.get("accept_after_edit", False),
        user_id=candidate.user_id if body.get("accept_after_edit") else None,
        companion_id=candidate.companion_id if body.get("accept_after_edit") else None,
    )
    if not result:
        return err("INVALID_STATE_TRANSITION", "Cannot edit this candidate")
    return ok(result)


@router.post("/{candidate_id}/reject")
def reject_memory_candidate(candidate_id: str, body: dict | None = None):
    reason = (body or {}).get("reason")
    c = memory_service.reject_memory_candidate(uuid.UUID(candidate_id), reason)
    if not c:
        return err("MEMORY_CANDIDATE_NOT_FOUND", "Memory candidate not found")
    return ok(memory_service._cand_dict(c))


@router.post("/{candidate_id}/merge")
def merge_memory_candidate(candidate_id: str, body: MemoryCandidateMergeRequest):
    try:
        result = memory_service.merge_memory_candidate(
            uuid.UUID(candidate_id),
            body.target_memory_id,
            companion_id=body.companion_id,
            expected_revision=body.expected_revision,
            merged_content=body.merged_content.strip(),
            reason=body.reason,
        )
    except memory_service.MemoryMutationError as exc:
        return err(exc.code, exc.message, exc.details)
    if not result:
        return err("INVALID_STATE_TRANSITION", "Cannot merge this candidate")
    return ok(result)
