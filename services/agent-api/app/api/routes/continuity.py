"""Continuity API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok, err
from app.services import continuity_service

router = APIRouter(tags=["Continuity"])


@router.post("/continuity/snapshots")
def create_snapshot(body: dict):
    result = continuity_service.create_snapshot(body)
    return ok(result)


@router.get("/continuity/snapshots")
def list_snapshots(
    companion_id: str | None = Query(None),
    conversation_id: str | None = Query(None),
    snapshot_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = continuity_service.list_snapshots(
        companion_id=uuid.UUID(companion_id) if companion_id else None,
        conversation_id=uuid.UUID(conversation_id) if conversation_id else None,
        snapshot_type=snapshot_type,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/continuity/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: str):
    cs = continuity_service.get_snapshot(uuid.UUID(snapshot_id))
    if not cs:
        return err("NOT_FOUND", "Continuity snapshot not found")
    return ok(cs)


@router.post("/continuity/refresh")
def refresh_continuity(body: dict):
    result = continuity_service.refresh_continuity(body)
    return ok(result)


@router.post("/continuity/correct")
def correct_continuity(body: dict):
    snapshot_id = body.get("snapshot_id")
    if not snapshot_id:
        return err("VALIDATION_ERROR", "snapshot_id is required")

    result = continuity_service.correct_continuity(uuid.UUID(snapshot_id), body)
    if not result:
        return err("NOT_FOUND", "Continuity snapshot not found")
    return ok(result)


@router.get("/conversations/{conversation_id}/continuity")
def get_conversation_continuity(conversation_id: str):
    result = continuity_service.get_conversation_continuity(uuid.UUID(conversation_id))
    if not result:
        return err("NOT_FOUND", "No continuity snapshot found for this conversation")
    return ok(result)
