"""Relationship Explanation API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok, err
from app.services import relationship_explanation_service

router = APIRouter(tags=["Relationship Explanations"])


@router.post("/relationship-explanations")
def create_explanation(body: dict):
    result = relationship_explanation_service.create_explanation(body)
    return ok(result)


@router.get("/relationship-explanations")
def list_explanations(
    companion_id: str | None = Query(None),
    dimension: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = relationship_explanation_service.list_explanations(
        companion_id=uuid.UUID(companion_id) if companion_id else None,
        dimension=dimension,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/relationship-explanations/{explanation_id}")
def get_explanation(explanation_id: str):
    re = relationship_explanation_service.get_explanation(uuid.UUID(explanation_id))
    if not re:
        return err("NOT_FOUND", "Relationship explanation not found")
    return ok(re)


@router.get("/companions/{companion_id}/relationship/explanations")
def list_for_companion(
    companion_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = relationship_explanation_service.list_for_companion(
        uuid.UUID(companion_id),
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])
