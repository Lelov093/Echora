"""Channel presence policy and check-in API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import channel_presence_policy_service

router = APIRouter(tags=["Channel Presence"])


@router.get("/channel-presence-policies")
def list_channel_presence_policies(
    channel_binding_id: str | None = Query(None),
    companion_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = channel_presence_policy_service.list_policies(
        channel_binding_id=uuid.UUID(channel_binding_id) if channel_binding_id else None,
        companion_id=uuid.UUID(companion_id) if companion_id else None,
        status=status,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/channel-presence-policies")
def create_channel_presence_policy(body: dict):
    data = channel_presence_policy_service.create_policy(body or {})
    if not data:
        return err("CHANNEL_PRESENCE_POLICY_CREATE_FAILED", "Unable to create channel presence policy")
    return ok(data)


@router.patch("/channel-presence-policies/{policy_id}")
def patch_channel_presence_policy(policy_id: str, body: dict):
    data = channel_presence_policy_service.patch_policy(uuid.UUID(policy_id), body or {})
    if not data:
        return err("CHANNEL_PRESENCE_POLICY_NOT_FOUND", "Channel presence policy not found")
    return ok(data)


@router.post("/channel-presence-policies/{policy_id}/enable-checkin")
def enable_channel_checkin(policy_id: str, body: dict):
    data = channel_presence_policy_service.enable_checkin(uuid.UUID(policy_id), body or {})
    if not data:
        return err("CHANNEL_CHECKIN_OPT_IN_REQUIRED", "Check-in requires explicit user opt-in")
    return ok(data)


@router.post("/channel-checkins/evaluate")
def evaluate_channel_checkin(body: dict):
    data = channel_presence_policy_service.evaluate_checkin(body or {})
    if not data:
        return err("CHANNEL_CHECKIN_EVALUATE_FAILED", "Unable to evaluate channel check-in")
    return ok(data)
