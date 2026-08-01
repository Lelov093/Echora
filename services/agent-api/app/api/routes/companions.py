"""Companion roster API routes."""

import uuid
from typing import Literal

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.schemas.companion_identity import CompanionCreateRequest
from app.services import companion_roster_service, companion_service

router = APIRouter(prefix="/companions", tags=["Companions"])


@router.get("")
def list_companions(
    user_id: str | None = Query(None),
    scope: Literal["product", "test", "archived", "unclassified", "all"] = Query("product"),
    search: str | None = Query(None, max_length=120),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    owner_id = uuid.UUID(user_id) if user_id else _get_seed_user_id()
    result = companion_roster_service.list_companions_page(
        user_id=owner_id,
        scope=scope,
        search=search,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(
        [companion_roster_service.get_companion_bundle(c.id) for c in result["items"]],
        page=page, page_size=page_size, total=result["total"],
    )


@router.post("")
def create_companion(body: CompanionCreateRequest):
    payload = body.model_dump(exclude_none=True)
    if not payload.get("user_id"):
        payload["user_id"] = _get_seed_user_id()
    try:
        c, first_meeting = companion_roster_service.create_companion(payload)
    except ValueError as exc:
        return err("INVALID_COMPANION_CLASSIFICATION", str(exc))
    return ok({
        **companion_roster_service.get_companion_bundle(c.id),
        "first_meeting_conversation_id": str(first_meeting.id),
    })


@router.get("/{companion_id}")
def get_companion(companion_id: str):
    data = companion_roster_service.get_companion_bundle(uuid.UUID(companion_id))
    if not data:
        return err("COMPANION_NOT_FOUND", "Companion not found")
    return ok(data)


@router.patch("/{companion_id}")
def update_companion(companion_id: str, body: dict):
    c = companion_roster_service.update_companion(uuid.UUID(companion_id), body)
    if not c:
        return err("COMPANION_NOT_FOUND", "Companion not found")
    return ok(companion_roster_service.get_companion_bundle(c.id))


@router.get("/{companion_id}/modes")
def list_modes(companion_id: str):
    modes = companion_service.list_modes(uuid.UUID(companion_id))
    return paginated_ok(
        [{"id": str(m.id), "mode_key": m.mode_key, "display_name": m.display_name,
          "is_enabled": m.is_enabled} for m in modes],
        page=1, page_size=len(modes) or 1, total=len(modes),
    )


@router.post("/{companion_id}/modes/{mode_key}/switch")
def switch_mode(companion_id: str, mode_key: str):
    c = companion_service.switch_mode(uuid.UUID(companion_id), mode_key)
    if not c:
        return err("INVALID_STATE_TRANSITION", f"Cannot switch to mode '{mode_key}'")
    return ok(companion_service._companion_to_dict(c))


@router.get("/{companion_id}/hub")
def get_hub(companion_id: str):
    data = companion_service.get_hub(uuid.UUID(companion_id))
    return ok(data)


# ── Helper ───────────────────────────────────────────────────────────

def _get_seed_user_id() -> uuid.UUID:
    """Get the seed user ID from the database."""
    from app.db.models import User
    s = companion_roster_service.get_session()
    u = s.query(User).first()
    s.close()
    if u:
        return u.id
    return uuid.uuid4()
