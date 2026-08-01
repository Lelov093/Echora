"""Deferred realtime co-presence REST contracts."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import realtime_copresence_service

router = APIRouter(tags=["Realtime Co-Presence"])


def _get_seed_user_id() -> uuid.UUID:
    from app.db.models import User

    s = realtime_copresence_service.get_session()
    u = s.query(User).first()
    s.close()
    return u.id if u else uuid.uuid4()


@router.get("/realtime-copresence-sessions")
def list_realtime_copresence_sessions(
    user_id: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = realtime_copresence_service.list_realtime_sessions(
        user_id=uuid.UUID(user_id) if user_id else None,
        status=status,
        page=page,
        page_size=page_size,
    )
    items = [realtime_copresence_service.get_realtime_session_bundle(item.id) for item in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.post("/realtime-copresence-sessions")
def create_realtime_copresence_session(body: dict):
    user_id = uuid.UUID(body["user_id"]) if body.get("user_id") else _get_seed_user_id()
    data = realtime_copresence_service.create_realtime_session(user_id, body or {})
    if not data:
        return err("REALTIME_COPRESENCE_CREATE_FAILED", "Unable to create realtime co-presence session")
    return ok(data)


@router.get("/realtime-copresence-sessions/{session_id}")
def get_realtime_copresence_session(session_id: str):
    data = realtime_copresence_service.get_realtime_session_bundle(uuid.UUID(session_id))
    if not data:
        return err("REALTIME_COPRESENCE_SESSION_NOT_FOUND", "Realtime co-presence session not found")
    return ok(data)


@router.post("/realtime-copresence-sessions/{session_id}/pause")
def pause_realtime_copresence_session(session_id: str):
    data = realtime_copresence_service.transition_realtime_session(uuid.UUID(session_id), "pause")
    if not data:
        return err("REALTIME_COPRESENCE_SESSION_NOT_FOUND", "Realtime co-presence session not found")
    return ok(data)


@router.post("/realtime-copresence-sessions/{session_id}/resume")
def resume_realtime_copresence_session(session_id: str):
    data = realtime_copresence_service.transition_realtime_session(uuid.UUID(session_id), "resume")
    if not data:
        return err("REALTIME_COPRESENCE_SESSION_NOT_FOUND", "Realtime co-presence session not found")
    return ok(data)


@router.post("/realtime-copresence-sessions/{session_id}/end")
def end_realtime_copresence_session(session_id: str):
    data = realtime_copresence_service.transition_realtime_session(uuid.UUID(session_id), "end")
    if not data:
        return err("REALTIME_COPRESENCE_SESSION_NOT_FOUND", "Realtime co-presence session not found")
    return ok(data)


@router.post("/realtime-copresence-sessions/{session_id}/participants")
def add_realtime_participant(session_id: str, body: dict):
    data = realtime_copresence_service.add_participant(uuid.UUID(session_id), body or {})
    if not data:
        return err("REALTIME_COPRESENCE_SESSION_NOT_FOUND", "Realtime co-presence session not found")
    return ok(data)


@router.patch("/realtime-copresence-sessions/{session_id}/participants/{participant_id}")
def patch_realtime_participant(session_id: str, participant_id: str, body: dict):
    data = realtime_copresence_service.patch_participant(
        uuid.UUID(session_id),
        uuid.UUID(participant_id),
        body or {},
    )
    if not data:
        return err("REALTIME_COPRESENCE_PARTICIPANT_NOT_FOUND", "Realtime participant not found")
    return ok(data)


@router.get("/realtime-copresence-sessions/{session_id}/channels")
def list_realtime_channels(session_id: str):
    data = realtime_copresence_service.list_channels(uuid.UUID(session_id))
    if data is None:
        return err("REALTIME_COPRESENCE_SESSION_NOT_FOUND", "Realtime co-presence session not found")
    return ok(data)


@router.patch("/realtime-copresence-sessions/{session_id}/channels/{channel_id}")
def patch_realtime_channel(session_id: str, channel_id: str, body: dict):
    data = realtime_copresence_service.patch_channel(
        uuid.UUID(session_id),
        uuid.UUID(channel_id),
        body or {},
    )
    if not data:
        return err("REALTIME_CHANNEL_NOT_FOUND", "Realtime channel not found")
    return ok(data)
