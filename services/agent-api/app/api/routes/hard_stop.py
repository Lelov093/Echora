"""Scoped hard stop routes."""

import uuid

from fastapi import APIRouter

from app.schemas.common import err, ok
from app.services import scoped_hard_stop_service

router = APIRouter(tags=["Scoped Hard Stop"])


@router.post("/hard-stops")
def trigger_scoped_hard_stop(body: dict):
    data = scoped_hard_stop_service.trigger_scoped_hard_stop(uuid.UUID(body["user_id"]), body or {})
    if not data:
        return err("SCOPED_HARD_STOP_FAILED", "Unable to trigger scoped hard stop")
    return ok(data)


@router.post("/hard-stops/session")
def stop_session_scope(body: dict):
    data = scoped_hard_stop_service.stop_session_scope(uuid.UUID(body["user_id"]), body or {})
    if not data:
        return err("SESSION_HARD_STOP_FAILED", "Unable to stop realtime session scope")
    return ok(data)


@router.post("/hard-stops/channel")
def stop_channel_scope(body: dict):
    data = scoped_hard_stop_service.stop_channel_scope(uuid.UUID(body["user_id"]), body or {})
    if not data:
        return err("CHANNEL_HARD_STOP_FAILED", "Unable to stop realtime channel scope")
    return ok(data)


@router.post("/hard-stops/companion")
def stop_companion_scope(body: dict):
    data = scoped_hard_stop_service.stop_companion_scope(uuid.UUID(body["user_id"]), body or {})
    if not data:
        return err("COMPANION_HARD_STOP_FAILED", "Unable to stop companion scope")
    return ok(data)


@router.post("/hard-stops/sensor")
def stop_sensor_scope(body: dict):
    data = scoped_hard_stop_service.stop_sensor_scope(uuid.UUID(body["user_id"]), body or {})
    if not data:
        return err("SENSOR_HARD_STOP_FAILED", "Unable to stop sensor/context scope")
    return ok(data)
