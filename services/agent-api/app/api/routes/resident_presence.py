"""Deferred resident presence contracts."""

import uuid

from fastapi import APIRouter

from app.schemas.common import err, ok
from app.services import resident_presence_service

router = APIRouter(tags=["Resident Presence"])


@router.post("/resident-presence/status")
def set_resident_status(body: dict):
    data = resident_presence_service.set_resident_status(
        uuid.UUID(body["user_id"]),
        uuid.UUID(body["companion_id"]),
        body or {},
    )
    if not data:
        return err("RESIDENT_STATUS_FAILED", "Unable to set resident status")
    return ok(data)


@router.post("/resident-presence/budget/evaluate")
def evaluate_presence_budget(body: dict):
    data = resident_presence_service.evaluate_presence_budget(
        uuid.UUID(body["user_id"]),
        uuid.UUID(body["companion_id"]),
        body or {},
    )
    if not data:
        return err("PRESENCE_BUDGET_FAILED", "Unable to evaluate presence budget")
    return ok(data)


@router.post("/resident-presence/invitations")
def create_copresence_invitation(body: dict):
    data = resident_presence_service.create_copresence_invitation(uuid.UUID(body["user_id"]), body or {})
    if not data:
        return err("COPRESENCE_INVITATION_FAILED", "Unable to create co-presence invitation")
    return ok(data)


@router.post("/resident-presence/meaningful-silence")
def apply_meaningful_silence(body: dict):
    data = resident_presence_service.apply_meaningful_silence(uuid.UUID(body["user_id"]), body or {})
    if not data:
        return err("MEANINGFUL_SILENCE_FAILED", "Unable to apply meaningful silence")
    return ok(data)
