"""Channel gateway core API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import channel_gateway_service

router = APIRouter(tags=["Channel Gateway"])


@router.get("/channel-providers")
def list_channel_providers(
    provider_kind: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = channel_gateway_service.list_providers(
        provider_kind=provider_kind,
        status=status,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/channel-providers/by-key/{provider_key}")
def get_channel_provider_by_key(provider_key: str):
    data = channel_gateway_service.get_provider_by_key(provider_key)
    if not data:
        return err("CHANNEL_PROVIDER_NOT_FOUND", "Channel provider not found")
    return ok(data)


@router.get("/channel-providers/{provider_id}")
def get_channel_provider(provider_id: str):
    data = channel_gateway_service.get_provider(uuid.UUID(provider_id))
    if not data:
        return err("CHANNEL_PROVIDER_NOT_FOUND", "Channel provider not found")
    return ok(data)


@router.get("/channel-bots")
def list_channel_bots(
    user_id: str | None = Query(None),
    provider_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = channel_gateway_service.list_bots(
        user_id=uuid.UUID(user_id) if user_id else None,
        provider_id=uuid.UUID(provider_id) if provider_id else None,
        status=status,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/channel-bots")
def register_channel_bot(body: dict):
    user_id = uuid.UUID(body["user_id"]) if body.get("user_id") else None
    data = channel_gateway_service.register_bot(user_id, body or {})
    if not data:
        return err("CHANNEL_BOT_REGISTER_FAILED", "Unable to register channel bot")
    return ok(data)


@router.get("/channel-bindings")
def list_channel_bindings(
    user_id: str | None = Query(None),
    companion_id: str | None = Query(None),
    provider_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = channel_gateway_service.list_bindings(
        user_id=uuid.UUID(user_id) if user_id else None,
        companion_id=uuid.UUID(companion_id) if companion_id else None,
        provider_id=uuid.UUID(provider_id) if provider_id else None,
        status=status,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/channel-bindings")
def create_channel_binding(body: dict):
    if not body.get("user_id"):
        return err("CHANNEL_BINDING_USER_REQUIRED", "user_id is required")
    data = channel_gateway_service.create_binding(uuid.UUID(body["user_id"]), body or {})
    if not data:
        return err("CHANNEL_BINDING_CREATE_FAILED", "Unable to create channel binding")
    return ok(data)


@router.get("/channel-bindings/{binding_id}")
def get_channel_binding(binding_id: str):
    data = channel_gateway_service.get_binding_bundle(uuid.UUID(binding_id))
    if not data:
        return err("CHANNEL_BINDING_NOT_FOUND", "Channel binding not found")
    return ok(data)


@router.post("/channel-bindings/{binding_id}/activate")
def activate_channel_binding(binding_id: str, body: dict | None = None):
    data = channel_gateway_service.transition_binding(
        uuid.UUID(binding_id),
        "activate",
        (body or {}).get("reason"),
    )
    if not data:
        return err("CHANNEL_BINDING_NOT_FOUND", "Channel binding not found")
    return ok(data)


@router.post("/channel-bindings/{binding_id}/disable")
def disable_channel_binding(binding_id: str, body: dict | None = None):
    data = channel_gateway_service.transition_binding(
        uuid.UUID(binding_id),
        "disable",
        (body or {}).get("reason"),
    )
    if not data:
        return err("CHANNEL_BINDING_NOT_FOUND", "Channel binding not found")
    return ok(data)


@router.post("/channel-bindings/{binding_id}/revoke")
def revoke_channel_binding(binding_id: str, body: dict | None = None):
    data = channel_gateway_service.revoke_binding(uuid.UUID(binding_id), (body or {}).get("reason"))
    if not data:
        return err("CHANNEL_BINDING_NOT_FOUND", "Channel binding not found")
    return ok(data)
