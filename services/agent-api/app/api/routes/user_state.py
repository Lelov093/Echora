"""User State API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, paginated_ok, err
from app.schemas.user_state import UserStateOverrideRequest, UserStateResetRequest
from app.services import user_state_service

router = APIRouter(tags=["User State"])


@router.post("/user-state/snapshots")
def create_snapshot(body: dict):
    result = user_state_service.create_snapshot(body)
    return ok(result)


@router.get("/user-state/snapshots")
def list_snapshots(
    user_id: str | None = Query(None),
    companion_id: str | None = Query(None),
    signal_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = user_state_service.list_snapshots(
        user_id=uuid.UUID(user_id) if user_id else None,
        companion_id=uuid.UUID(companion_id) if companion_id else None,
        signal_type=signal_type,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/user-state/snapshots/{snapshot_id}")
def get_snapshot(snapshot_id: str):
    uss = user_state_service.get_snapshot(uuid.UUID(snapshot_id))
    if not uss:
        return err("NOT_FOUND", "User state snapshot not found")
    return ok(uss)


@router.get("/users/{user_id}/state/snapshots")
def list_for_user(
    user_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = user_state_service.list_for_user(
        uuid.UUID(user_id),
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.get("/user-state/current")
def get_current_state(user_id: str, companion_id: str):
    return ok(
        user_state_service.get_current_state(
            uuid.UUID(user_id),
            uuid.UUID(companion_id),
        )
    )


@router.post("/user-state/override")
def override_state(body: UserStateOverrideRequest):
    try:
        result = user_state_service.override_state(
            body.user_id,
            body.companion_id,
            body.signal_type,
            body.value,
            reason=body.reason,
            mode_key=body.mode_key,
        )
    except ValueError as exc:
        return err("USER_STATE_OVERRIDE_INVALID", str(exc))
    return ok(result)


@router.post("/user-state/reset")
def reset_state(body: UserStateResetRequest):
    try:
        result = user_state_service.reset_state(
            body.user_id,
            body.companion_id,
            body.signal_type,
            reason=body.reason,
            baseline=body.baseline,
            mode_key=body.mode_key,
        )
    except ValueError as exc:
        return err("USER_STATE_RESET_INVALID", str(exc))
    return ok(result)
