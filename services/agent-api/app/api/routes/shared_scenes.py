"""Shared scene API routes."""

import uuid
from typing import Literal

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import shared_scene_service

router = APIRouter(tags=["Shared Scenes"])


def _get_seed_user_id() -> uuid.UUID:
    from app.db.models import User

    s = shared_scene_service.get_session()
    u = s.query(User).first()
    s.close()
    return u.id if u else uuid.uuid4()


@router.get("/shared-scenes")
def list_shared_scenes(
    user_id: str | None = Query(None),
    scope: Literal["product", "test", "archived", "unclassified", "all"] = Query("product"),
    co_presence_session_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = shared_scene_service.list_shared_scenes(
        user_id=uuid.UUID(user_id) if user_id else _get_seed_user_id(),
        companion_scope=scope,
        co_presence_session_id=uuid.UUID(co_presence_session_id) if co_presence_session_id else None,
        status=status,
        page=page,
        page_size=page_size,
    )
    items = [shared_scene_service.get_shared_scene_bundle(item.id) for item in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.post("/shared-scenes")
def create_shared_scene(body: dict):
    user_id = uuid.UUID(body["user_id"]) if body.get("user_id") else _get_seed_user_id()
    data = shared_scene_service.create_shared_scene(user_id, body or {})
    if not data:
        return err("SHARED_SCENE_CREATE_FAILED", "Unable to create shared scene")
    return ok(data)


@router.get("/shared-scenes/{scene_id}")
def get_shared_scene(scene_id: str):
    data = shared_scene_service.get_shared_scene_bundle(uuid.UUID(scene_id))
    if not data:
        return err("SHARED_SCENE_NOT_FOUND", "Shared scene not found")
    return ok(data)


@router.patch("/shared-scenes/{scene_id}")
def patch_shared_scene(scene_id: str, body: dict):
    data = shared_scene_service.patch_shared_scene(uuid.UUID(scene_id), body or {})
    if not data:
        return err("SHARED_SCENE_NOT_FOUND", "Shared scene not found")
    return ok(data)


@router.get("/shared-scenes/{scene_id}/events")
def list_shared_scene_events(scene_id: str):
    data = shared_scene_service.get_shared_scene_bundle(uuid.UUID(scene_id))
    if not data:
        return err("SHARED_SCENE_NOT_FOUND", "Shared scene not found")
    return ok({"items": data["events"]})


@router.post("/shared-scenes/{scene_id}/events")
def create_shared_scene_event(scene_id: str, body: dict):
    data = shared_scene_service.create_shared_scene_event(uuid.UUID(scene_id), body or {})
    if not data:
        return err("SHARED_SCENE_NOT_FOUND", "Shared scene not found")
    return ok(data)
