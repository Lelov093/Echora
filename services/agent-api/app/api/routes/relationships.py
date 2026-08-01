"""Relationship API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok, err
from app.schemas.relationship_evolution import (
    RelationshipCommitRequest,
    RelationshipCorrectionRequest,
    RelationshipRejectRequest,
)
from app.services import relationship_service

router = APIRouter(tags=["Relationships"])


@router.get("/companions/{companion_id}/relationship")
def get_relationship(companion_id: str):
    rs = relationship_service.get_relationship_state(uuid.UUID(companion_id))
    if not rs:
        return ok(None)
    return ok(rs)


@router.get("/companions/{companion_id}/relationship/events")
def list_relationship_events(companion_id: str, dimension: str | None = Query(None),
                             page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
    result = relationship_service.list_relationship_events(
        uuid.UUID(companion_id), dimension, page, page_size,
    )
    items = [{
        "id": str(e.id), "dimension": e.dimension, "delta": e.delta,
        "previous_value": e.previous_value, "new_value": e.new_value,
        "reason": e.reason,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    } for e in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.get("/companions/{companion_id}/relationship/candidates")
def list_relationship_candidates(
    companion_id: str,
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = relationship_service.list_relationship_candidates(
        uuid.UUID(companion_id), status=status, page=page, page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/companions/{companion_id}/relationship/candidates/{candidate_id}/commit")
def commit_relationship_candidate(
    companion_id: str,
    candidate_id: str,
    body: RelationshipCommitRequest,
):
    try:
        result = relationship_service.commit_relationship_candidate(
            uuid.UUID(candidate_id), uuid.UUID(companion_id),
            expected_revision=body.expected_revision, reason=body.reason,
        )
    except relationship_service.RelationshipMutationError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(result)


@router.post("/companions/{companion_id}/relationship/candidates/{candidate_id}/reject")
def reject_relationship_candidate(
    companion_id: str,
    candidate_id: str,
    body: RelationshipRejectRequest,
):
    try:
        result = relationship_service.reject_relationship_candidate(
            uuid.UUID(candidate_id), uuid.UUID(companion_id), reason=body.reason,
        )
    except relationship_service.RelationshipMutationError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(result)


@router.get("/companions/{companion_id}/relationship/revisions")
def list_relationship_revisions(
    companion_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = relationship_service.list_relationship_revisions(
        uuid.UUID(companion_id), page=page, page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/companions/{companion_id}/relationship/revisions/{revision_id}/correct")
def correct_relationship_revision(
    companion_id: str,
    revision_id: str,
    body: RelationshipCorrectionRequest,
):
    try:
        result = relationship_service.correct_relationship_revision(
            uuid.UUID(revision_id), uuid.UUID(companion_id),
            expected_revision=body.expected_revision, reason=body.reason,
        )
    except relationship_service.RelationshipMutationError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(result)
