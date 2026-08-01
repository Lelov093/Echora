"""Proactive Presence schedule API."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import err, ok
from app.schemas.presence_schedule import PresenceScheduleUpdateRequest, PresenceTriggerRequest
from app.services import presence_schedule_service

router = APIRouter(prefix="/presence/schedules", tags=["Presence Schedule"])


@router.get("/{companion_id}")
def get_schedule(companion_id: str, user_id: str = Query(...)):
    schedule = presence_schedule_service.get_schedule(uuid.UUID(user_id), uuid.UUID(companion_id))
    return ok(presence_schedule_service.schedule_dict(schedule) if schedule else None)


@router.put("/{companion_id}")
def put_schedule(companion_id: str, body: PresenceScheduleUpdateRequest, user_id: str = Query(...)):
    try:
        schedule = presence_schedule_service.upsert_schedule(
            uuid.UUID(user_id), uuid.UUID(companion_id), body.model_dump()
        )
    except presence_schedule_service.PresenceScheduleError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(presence_schedule_service.schedule_dict(schedule))


@router.post("/{companion_id}/trigger")
def trigger_schedule(companion_id: str, body: PresenceTriggerRequest, user_id: str = Query(...)):
    try:
        result = presence_schedule_service.trigger_now(
            uuid.UUID(user_id), uuid.UUID(companion_id), body.expected_revision
        )
    except presence_schedule_service.PresenceScheduleError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(result)


@router.get("/{companion_id}/occurrences")
def list_occurrences(
    companion_id: str,
    user_id: str = Query(...),
    limit: int = Query(20, ge=1, le=100),
):
    return ok(
        presence_schedule_service.list_occurrences(
            uuid.UUID(user_id), uuid.UUID(companion_id), limit
        )
    )
