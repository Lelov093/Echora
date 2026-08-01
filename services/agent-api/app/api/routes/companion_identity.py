"""Companion identity, persona, relationship contract, and boundary routes."""

import uuid

from fastapi import APIRouter

from app.schemas.common import err, ok
from app.schemas.companion_identity import CompanionLifecycleTransitionRequest, CompanionOwnerSettingsPatch
from app.services import companion_contract_service, companion_growth_service, companion_identity_service

router = APIRouter(prefix="/companions", tags=["Companion Identity"])


@router.patch("/{companion_id}/owner-settings")
def patch_owner_settings(companion_id: str, body: CompanionOwnerSettingsPatch):
    try:
        data = companion_identity_service.patch_owner_settings(
            uuid.UUID(companion_id), body.model_dump(exclude_none=True)
        )
    except ValueError as exc:
        return err("COMPANION_PROFILE_VERSION_CONFLICT", str(exc))
    if not data:
        return err("COMPANION_NOT_FOUND", "Companion not found")
    return ok(data)


@router.post("/{companion_id}/archive")
def archive_companion(companion_id: str, body: CompanionLifecycleTransitionRequest):
    try:
        data = companion_identity_service.set_companion_archived(
            uuid.UUID(companion_id), body.expected_identity_updated_at, archived=True,
            confirmed=body.confirm_preserve_history,
        )
    except ValueError as exc:
        return err("COMPANION_LIFECYCLE_CONFLICT", str(exc))
    if not data:
        return err("COMPANION_NOT_FOUND", "Companion not found")
    return ok(data)


@router.post("/{companion_id}/restore")
def restore_companion(companion_id: str, body: CompanionLifecycleTransitionRequest):
    try:
        data = companion_identity_service.set_companion_archived(
            uuid.UUID(companion_id), body.expected_identity_updated_at, archived=False,
            confirmed=body.confirm_preserve_history and body.confirm_boundaries_and_channels,
        )
    except ValueError as exc:
        return err("COMPANION_LIFECYCLE_CONFLICT", str(exc))
    if not data:
        return err("COMPANION_NOT_FOUND", "Companion not found")
    return ok(data)


@router.get("/{companion_id}/identity")
def get_identity(companion_id: str):
    data = companion_identity_service.get_identity(uuid.UUID(companion_id))
    if not data:
        return err("COMPANION_NOT_FOUND", "Companion not found")
    return ok(data)


@router.patch("/{companion_id}/identity")
def patch_identity(companion_id: str, body: dict):
    data = companion_identity_service.patch_identity(uuid.UUID(companion_id), body or {})
    if not data:
        return err("COMPANION_NOT_FOUND", "Companion not found")
    return ok(data)


@router.get("/{companion_id}/persona")
def get_persona(companion_id: str):
    data = companion_identity_service.get_persona(uuid.UUID(companion_id))
    if not data:
        return err("COMPANION_NOT_FOUND", "Companion not found")
    return ok(data)


@router.patch("/{companion_id}/persona")
def patch_persona(companion_id: str, body: dict):
    data = companion_identity_service.patch_persona(uuid.UUID(companion_id), body or {})
    if not data:
        return err("COMPANION_NOT_FOUND", "Companion not found")
    return ok(data)


@router.post("/{companion_id}/persona-growth-candidates/{candidate_id}/decision")
def decide_persona_growth_candidate(companion_id: str, candidate_id: str, body: dict):
    data = companion_growth_service.decide_persona_growth_candidate(
        uuid.UUID(companion_id), uuid.UUID(candidate_id), (body or {}).get("decision", "").lower()
    )
    if not data:
        return err("INVALID_PERSONA_GROWTH_REVIEW", "Candidate is unavailable, outside this Companion scope, or no longer pending review")
    return ok(data)


@router.get("/{companion_id}/visibility")
def get_visibility(companion_id: str):
    data = companion_identity_service.get_visibility(uuid.UUID(companion_id))
    if not data:
        return err("COMPANION_NOT_FOUND", "Companion not found")
    return ok(data)


@router.patch("/{companion_id}/visibility")
def patch_visibility(companion_id: str, body: dict):
    data = companion_identity_service.patch_visibility(uuid.UUID(companion_id), body or {})
    if not data:
        return err("COMPANION_NOT_FOUND", "Companion not found")
    return ok(data)


@router.get("/{companion_id}/contract")
def get_contract(companion_id: str):
    data = companion_contract_service.get_contract(uuid.UUID(companion_id))
    if not data:
        return err("COMPANION_NOT_FOUND", "Companion not found")
    return ok(data)


@router.patch("/{companion_id}/contract")
def patch_contract(companion_id: str, body: dict):
    data = companion_contract_service.patch_contract(uuid.UUID(companion_id), body or {})
    if not data:
        return err("COMPANION_NOT_FOUND", "Companion not found")
    return ok(data)


@router.get("/{companion_id}/boundary")
def get_boundary(companion_id: str):
    data = companion_contract_service.get_boundary(uuid.UUID(companion_id))
    if not data:
        return err("COMPANION_NOT_FOUND", "Companion not found")
    return ok(data)


@router.patch("/{companion_id}/boundary")
def patch_boundary(companion_id: str, body: dict):
    data = companion_contract_service.patch_boundary(uuid.UUID(companion_id), body or {})
    if not data:
        return err("COMPANION_NOT_FOUND", "Companion not found")
    return ok(data)
