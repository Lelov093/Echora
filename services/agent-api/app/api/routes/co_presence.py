"""Co-presence API routes."""

import uuid
from typing import Literal

from fastapi import APIRouter, Query

from app.schemas.common import err, ok, paginated_ok
from app.schemas.companion_room import (
    CompanionRoomCreateRequest,
    CompanionRoomMemberActionRequest,
    CompanionRoomMemberInviteRequest,
    CompanionRoomRestoreRequest,
    CompanionRoomUpdateRequest,
    CompanionRoomTurnRequest,
    CompanionRoomSuccessorRequest,
)
from app.services import companion_room_application_service, companion_room_turn_service, co_presence_service

router = APIRouter(tags=["Co-Presence"])


def _get_seed_user_id() -> uuid.UUID:
    from app.db.models import User

    s = co_presence_service.get_session()
    u = s.query(User).first()
    s.close()
    return u.id if u else uuid.uuid4()


@router.get("/co-presence-sessions")
def list_co_presence_sessions(
    user_id: str | None = Query(None),
    status: str | None = Query(None),
    session_source: str | None = Query(None, max_length=80),
    scope: Literal["product", "all"] = Query("all"),
    search: str | None = Query(None, max_length=120),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    result = co_presence_service.list_co_presence_sessions(
        user_id=uuid.UUID(user_id) if user_id else None,
        status=status,
        session_source=session_source,
        companion_scope=scope,
        search=search,
        page=page,
        page_size=page_size,
    )
    items = [co_presence_service.get_co_presence_session_bundle(item.id) for item in result["items"]]
    return paginated_ok(items, page, page_size, result["total"])


@router.post("/co-presence-sessions")
def create_co_presence_session(body: dict):
    user_id = uuid.UUID(body["user_id"]) if body.get("user_id") else _get_seed_user_id()
    data = co_presence_service.create_co_presence_session(user_id, body or {})
    if not data:
        return err("CO_PRESENCE_CREATE_FAILED", "Unable to create co-presence session")
    return ok(data)


@router.get("/co-presence-sessions/{session_id}")
def get_co_presence_session(session_id: str):
    data = co_presence_service.get_co_presence_session_bundle(uuid.UUID(session_id))
    if not data:
        return err("CO_PRESENCE_SESSION_NOT_FOUND", "Co-presence session not found")
    return ok(data)


@router.patch("/co-presence-sessions/{session_id}")
def patch_co_presence_session(session_id: str, body: dict):
    data = co_presence_service.patch_co_presence_session(uuid.UUID(session_id), body or {})
    if not data:
        return err("CO_PRESENCE_SESSION_NOT_FOUND", "Co-presence session not found")
    return ok(data)


@router.post("/co-presence-sessions/{session_id}/participants")
def add_participant(session_id: str, body: dict):
    data = co_presence_service.add_participant_to_session(uuid.UUID(session_id), body or {})
    if not data:
        return err("CO_PRESENCE_SESSION_NOT_FOUND", "Co-presence session not found")
    return ok(data)


@router.patch("/co-presence-sessions/{session_id}/participants/{participant_id}")
def patch_participant(session_id: str, participant_id: str, body: dict):
    data = co_presence_service.patch_participant(
        uuid.UUID(session_id),
        uuid.UUID(participant_id),
        body or {},
    )
    if not data:
        return err("CO_PRESENCE_PARTICIPANT_NOT_FOUND", "Co-presence participant not found")
    return ok(data)


@router.post("/co-presence-sessions/{session_id}/end")
def end_co_presence_session(session_id: str):
    data = co_presence_service.end_co_presence_session(uuid.UUID(session_id))
    if not data:
        return err("CO_PRESENCE_SESSION_NOT_FOUND", "Co-presence session not found")
    return ok(data)


@router.post("/companion-rooms")
def create_companion_room(body: CompanionRoomCreateRequest):
    try:
        data = companion_room_application_service.create_companion_room(body.model_dump(mode="json"))
    except companion_room_application_service.CompanionRoomError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(data)


@router.get("/companion-rooms/{session_id}")
def get_companion_room(session_id: str):
    try:
        data = companion_room_application_service.get_companion_room(uuid.UUID(session_id))
    except companion_room_application_service.CompanionRoomError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(data)


@router.patch("/companion-rooms/{session_id}")
def update_companion_room(session_id: str, body: CompanionRoomUpdateRequest):
    try:
        data = companion_room_application_service.update_companion_room(
            uuid.UUID(session_id), body.model_dump(exclude_unset=True)
        )
    except companion_room_application_service.CompanionRoomError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(data)


@router.post("/companion-rooms/{session_id}/archive")
def archive_companion_room(session_id: str):
    try:
        data = companion_room_application_service.archive_companion_room(uuid.UUID(session_id))
    except companion_room_application_service.CompanionRoomError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(data)


@router.post("/companion-rooms/{session_id}/restore")
def restore_companion_room(session_id: str, body: CompanionRoomRestoreRequest):
    try:
        data = companion_room_application_service.restore_companion_room(
            uuid.UUID(session_id), body.model_dump(mode="json")
        )
    except companion_room_application_service.CompanionRoomError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(data)


@router.post("/companion-rooms/{session_id}/members")
def invite_companion_room_member(session_id: str, body: CompanionRoomMemberInviteRequest):
    try:
        data = companion_room_application_service.invite_room_member(
            uuid.UUID(session_id), body.model_dump(mode="json")
        )
    except companion_room_application_service.CompanionRoomError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(data)


@router.post("/companion-rooms/{session_id}/members/{participant_id}/transition")
def transition_companion_room_member(
    session_id: str,
    participant_id: str,
    body: CompanionRoomMemberActionRequest,
):
    try:
        data = companion_room_application_service.transition_room_member(
            uuid.UUID(session_id), uuid.UUID(participant_id), body.model_dump(mode="json")
        )
    except companion_room_application_service.CompanionRoomError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(data)


def _room_turn_error(exc: companion_room_turn_service.CompanionRoomTurnError):
    return err(exc.code, exc.message, exc.details)


@router.get("/companion-rooms/{session_id}/messages")
def list_companion_room_messages(session_id: str, limit: int = Query(100, ge=1, le=200)):
    try:
        data = companion_room_turn_service.list_room_messages(uuid.UUID(session_id), limit=limit)
    except companion_room_turn_service.CompanionRoomTurnError as exc:
        return _room_turn_error(exc)
    return ok(data)


@router.post("/companion-rooms/{session_id}/turns")
def run_companion_room_turn(session_id: str, body: CompanionRoomTurnRequest):
    try:
        data = companion_room_turn_service.execute_room_turn(
            uuid.UUID(session_id), body.model_dump(mode="json")
        )
    except companion_room_turn_service.CompanionRoomTurnError as exc:
        return _room_turn_error(exc)
    return ok(data)


@router.post("/companion-rooms/{session_id}/successor")
def create_companion_room_successor(session_id: str, body: CompanionRoomSuccessorRequest):
    try:
        data = companion_room_application_service.create_successor_room(
            uuid.UUID(session_id), body.model_dump(mode="json")
        )
    except companion_room_application_service.CompanionRoomError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(data)


@router.get("/companion-rooms/{session_id}/turns/{turn_id}")
def get_companion_room_turn(session_id: str, turn_id: str):
    try:
        data = companion_room_turn_service.get_room_turn(uuid.UUID(session_id), uuid.UUID(turn_id))
    except companion_room_turn_service.CompanionRoomTurnError as exc:
        return _room_turn_error(exc)
    return ok(data)


@router.post("/companion-rooms/{session_id}/turns/{turn_id}/cancel")
def cancel_companion_room_turn(session_id: str, turn_id: str):
    try:
        data = companion_room_turn_service.cancel_room_turn(uuid.UUID(session_id), uuid.UUID(turn_id))
    except companion_room_turn_service.CompanionRoomTurnError as exc:
        return _room_turn_error(exc)
    return ok(data)


@router.post("/companion-rooms/{session_id}/turns/{turn_id}/steps/{step_id}/retry")
def retry_companion_room_turn_step(session_id: str, turn_id: str, step_id: str):
    try:
        data = companion_room_turn_service.retry_room_turn_step(
            uuid.UUID(session_id), uuid.UUID(turn_id), uuid.UUID(step_id)
        )
    except companion_room_turn_service.CompanionRoomTurnError as exc:
        return _room_turn_error(exc)
    return ok(data)
