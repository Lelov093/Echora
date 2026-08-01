"""Deferred companion voice service contracts."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.services import companion_voice_service

router = APIRouter(tags=["Companion Voice"])


def _get_seed_user_id() -> uuid.UUID:
    from app.db.models import User

    s = companion_voice_service.get_session()
    u = s.query(User).first()
    s.close()
    return u.id if u else uuid.uuid4()


@router.get("/companion-voice-sessions")
def list_companion_voice_sessions(
    user_id: str | None = Query(None),
    realtime_session_id: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = companion_voice_service.list_voice_sessions(
        user_id=uuid.UUID(user_id) if user_id else None,
        realtime_session_id=uuid.UUID(realtime_session_id) if realtime_session_id else None,
        page=page,
        page_size=page_size,
    )
    return paginated_ok(result["items"], page, page_size, result["total"])


@router.post("/companion-voice-sessions")
def create_companion_voice_session(body: dict):
    user_id = uuid.UUID(body["user_id"]) if body.get("user_id") else _get_seed_user_id()
    data = companion_voice_service.create_voice_session(user_id, body or {})
    if not data:
        return err("COMPANION_VOICE_CREATE_FAILED", "Unable to create companion voice session")
    return ok(data)


@router.get("/companion-voice-sessions/{voice_session_id}")
def get_companion_voice_session(voice_session_id: str):
    data = companion_voice_service.get_voice_session_bundle(uuid.UUID(voice_session_id))
    if not data:
        return err("COMPANION_VOICE_SESSION_NOT_FOUND", "Companion voice session not found")
    return ok(data)


@router.post("/companion-voice-sessions/{voice_session_id}/stt/partial")
def record_stt_partial(voice_session_id: str, body: dict):
    data = companion_voice_service.record_stt_partial(uuid.UUID(voice_session_id), body or {})
    if not data:
        return err("COMPANION_VOICE_SESSION_NOT_FOUND", "Companion voice session not found")
    return ok(data)


@router.post("/companion-voice-sessions/{voice_session_id}/stt/final")
def record_stt_final(voice_session_id: str, body: dict):
    data = companion_voice_service.record_stt_final(uuid.UUID(voice_session_id), body or {})
    if not data:
        return err("COMPANION_VOICE_SESSION_NOT_FOUND", "Companion voice session not found")
    return ok(data)


@router.post("/companion-voice-sessions/{voice_session_id}/tts-events")
def record_tts_event(voice_session_id: str, body: dict):
    data = companion_voice_service.record_tts_event(uuid.UUID(voice_session_id), body or {})
    if not data:
        return err("COMPANION_VOICE_SESSION_NOT_FOUND", "Companion voice session not found")
    return ok(data)


@router.post("/companion-voice-sessions/{voice_session_id}/turn-taking")
def decide_turn_taking_state(voice_session_id: str, body: dict):
    data = companion_voice_service.decide_turn_taking_state(uuid.UUID(voice_session_id), body or {})
    if not data:
        return err("COMPANION_VOICE_SESSION_NOT_FOUND", "Companion voice session not found")
    return ok(data)


@router.post("/companion-voice-sessions/{voice_session_id}/interruptions")
def record_interruption(voice_session_id: str, body: dict):
    data = companion_voice_service.record_interruption(uuid.UUID(voice_session_id), body or {})
    if not data:
        return err("COMPANION_VOICE_SESSION_NOT_FOUND", "Companion voice session not found")
    return ok(data)


@router.post("/companion-voice-sessions/{voice_session_id}/persona-guard")
def run_voice_persona_guard(voice_session_id: str, body: dict):
    data = companion_voice_service.run_voice_persona_guard(uuid.UUID(voice_session_id), body or {})
    if not data:
        return err("COMPANION_VOICE_SESSION_NOT_FOUND", "Companion voice session not found")
    return ok(data)
