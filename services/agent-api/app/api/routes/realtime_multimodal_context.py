"""Deferred realtime multimodal context permission contracts."""

import uuid

from fastapi import APIRouter

from app.schemas.common import err, ok
from app.services import multimodal_permission_service

router = APIRouter(tags=["Realtime Multimodal Context"])


def _get_seed_user_id() -> uuid.UUID:
    from app.db.models import User

    s = multimodal_permission_service.get_session()
    u = s.query(User).first()
    s.close()
    return u.id if u else uuid.uuid4()


@router.post("/realtime-multimodal-context-events")
def create_context_event(body: dict):
    user_id = uuid.UUID(body["user_id"]) if body.get("user_id") else _get_seed_user_id()
    data = multimodal_permission_service.create_context_event(user_id, body or {})
    if not data:
        return err("REALTIME_CONTEXT_CREATE_FAILED", "Unable to create realtime multimodal context event")
    return ok(data)


@router.get("/realtime-multimodal-context-events/{context_event_id}")
def get_context_event(context_event_id: str):
    data = multimodal_permission_service.get_context_event_bundle(uuid.UUID(context_event_id))
    if not data:
        return err("REALTIME_CONTEXT_NOT_FOUND", "Realtime multimodal context event not found")
    return ok(data)


@router.post("/realtime-multimodal-context-events/{context_event_id}/permissions")
def record_permission_event(context_event_id: str, body: dict):
    data = multimodal_permission_service.record_permission_event(uuid.UUID(context_event_id), body or {})
    if not data:
        return err("REALTIME_CONTEXT_PERMISSION_FAILED", "Unable to record participant context permission")
    return ok(data)


@router.get("/realtime-multimodal-context-events/{context_event_id}/participants/{participant_id}/visibility")
def check_participant_visibility(context_event_id: str, participant_id: str):
    data = multimodal_permission_service.check_participant_visibility(uuid.UUID(context_event_id), uuid.UUID(participant_id))
    if not data:
        return err("REALTIME_CONTEXT_VISIBILITY_NOT_FOUND", "Context or participant not found")
    return ok(data)


@router.get("/realtime-multimodal-context-events/{context_event_id}/retention")
def check_context_retention(context_event_id: str):
    data = multimodal_permission_service.check_context_retention(uuid.UUID(context_event_id))
    if not data:
        return err("REALTIME_CONTEXT_NOT_FOUND", "Realtime multimodal context event not found")
    return ok(data)


@router.post("/realtime-multimodal-context-events/{context_event_id}/expire")
def expire_ephemeral_context(context_event_id: str):
    data = multimodal_permission_service.expire_ephemeral_context(uuid.UUID(context_event_id))
    if not data:
        return err("REALTIME_CONTEXT_NOT_FOUND", "Realtime multimodal context event not found")
    return ok(data)
