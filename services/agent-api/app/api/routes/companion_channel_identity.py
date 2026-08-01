"""Companion channel identity API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import companion_channel_identity_service

router = APIRouter(tags=["Companion Channel Identity"])


@router.get("/companion-channel-identities")
def list_companion_channel_identities(
    companion_id: str | None = Query(None),
    channel_status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = companion_channel_identity_service.list_identities(
        companion_id=uuid.UUID(companion_id) if companion_id else None,
        channel_status=channel_status,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/companions/{companion_id}/channel-identities")
def list_companion_channel_identities_for_companion(
    companion_id: str,
    channel_status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = companion_channel_identity_service.list_identities(
        companion_id=uuid.UUID(companion_id),
        channel_status=channel_status,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/companion-channel-identities")
def create_companion_channel_identity(body: dict):
    data = companion_channel_identity_service.create_identity(body or {})
    if not data:
        return err("COMPANION_CHANNEL_IDENTITY_CREATE_FAILED", "Unable to create companion channel identity")
    return ok(data)


@router.get("/companion-channel-identities/{identity_id}")
def get_companion_channel_identity(identity_id: str):
    data = companion_channel_identity_service.get_identity(uuid.UUID(identity_id))
    if not data:
        return err("COMPANION_CHANNEL_IDENTITY_NOT_FOUND", "Companion channel identity not found")
    return ok(data)


@router.patch("/companion-channel-identities/{identity_id}")
def update_companion_channel_identity(identity_id: str, body: dict):
    data = companion_channel_identity_service.update_identity(uuid.UUID(identity_id), body or {})
    if not data:
        return err("COMPANION_CHANNEL_IDENTITY_UPDATE_FAILED", "Unable to update companion channel identity")
    return ok(data)


@router.post("/companion-channel-identities/{identity_id}/disable")
def disable_companion_channel_identity(identity_id: str, body: dict | None = None):
    data = companion_channel_identity_service.disable_identity(uuid.UUID(identity_id), (body or {}).get("reason"))
    if not data:
        return err("COMPANION_CHANNEL_IDENTITY_NOT_FOUND", "Companion channel identity not found")
    return ok(data)


@router.post("/companion-channel-identities/{identity_id}/unbind")
def unbind_companion_channel_identity(identity_id: str, body: dict | None = None):
    data = companion_channel_identity_service.unbind_identity(uuid.UUID(identity_id), (body or {}).get("reason"))
    if not data:
        return err("COMPANION_CHANNEL_IDENTITY_NOT_FOUND", "Companion channel identity not found")
    return ok(data)
