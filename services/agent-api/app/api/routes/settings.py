"""Settings / Boundary API routes."""

import uuid

from fastapi import APIRouter, Query

from app.schemas.common import ok, err
from app.schemas.governance_policy import (
    GovernancePolicyRollbackRequest,
    GovernancePolicyUpdateRequest,
)
from app.schemas.memory_selection_policy import (
    MemorySelectionPolicyRollbackRequest,
    MemorySelectionPolicyUpdateRequest,
)
from app.schemas.presence_timing_policy import (
    PresenceTimingPolicyRollbackRequest,
    PresenceTimingPolicyUpdateRequest,
)
from app.schemas.product_crud import PresencePolicyUpdateRequest
from app.schemas.presence_configuration import PresenceConfigurationUpdateRequest
from app.services import (
    governance_policy_service,
    memory_selection_policy_service,
    presence_timing_policy_service,
    presence_configuration_service,
    settings_service,
)

router = APIRouter(tags=["Settings"])


@router.get("/settings")
def get_settings(companion_id: str = Query(...)):
    bs = settings_service.get_settings(uuid.UUID(companion_id))
    if not bs:
        return ok(None)
    return ok(settings_service._bs_dict(bs))


@router.patch("/settings")
def update_settings(companion_id: str = Query(...), body: PresencePolicyUpdateRequest | None = None):
    try:
        bs = settings_service.update_settings(
            uuid.UUID(companion_id), None,
            body.model_dump(exclude_none=True) if body else {},
        )
    except ValueError as exc:
        return err("PRESENCE_POLICY_SCOPE_MISMATCH", str(exc))
    return ok(settings_service._bs_dict(bs))


@router.get("/companions/{companion_id}/presence-policy")
def get_presence_policy(companion_id: str):
    bs = settings_service.get_settings(uuid.UUID(companion_id))
    if not bs:
        return ok(None)
    return ok(settings_service._bs_dict(bs))


@router.patch("/companions/{companion_id}/presence-policy")
def update_presence_policy(companion_id: str, body: PresencePolicyUpdateRequest):
    try:
        bs = settings_service.update_settings(
            uuid.UUID(companion_id), None, body.model_dump(exclude_none=True),
        )
    except ValueError as exc:
        return err("PRESENCE_POLICY_SCOPE_MISMATCH", str(exc))
    return ok(settings_service._bs_dict(bs))


@router.get("/companions/{companion_id}/presence-configuration")
def get_presence_configuration(companion_id: str, user_id: str = Query(...)):
    try:
        data = presence_configuration_service.get_configuration(
            uuid.UUID(user_id), uuid.UUID(companion_id)
        )
    except presence_configuration_service.PresenceConfigurationError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(data)


@router.put("/companions/{companion_id}/presence-configuration")
def update_presence_configuration(
    companion_id: str,
    body: PresenceConfigurationUpdateRequest,
    user_id: str = Query(...),
):
    try:
        data = presence_configuration_service.update_configuration(
            uuid.UUID(user_id),
            uuid.UUID(companion_id),
            body.model_dump(),
        )
    except presence_configuration_service.PresenceConfigurationError as exc:
        return err(exc.code, exc.message, exc.details)
    return ok(data)


@router.get("/companions/{companion_id}/governance-policy")
def get_governance_policy(companion_id: str):
    try:
        policy = governance_policy_service.get_governance_policy(uuid.UUID(companion_id))
    except ValueError as exc:
        return err("GOVERNANCE_POLICY_SCOPE_MISMATCH", str(exc))
    return ok(policy)


@router.patch("/companions/{companion_id}/governance-policy")
def update_governance_policy(companion_id: str, body: GovernancePolicyUpdateRequest):
    try:
        policy = governance_policy_service.update_governance_policy(
            uuid.UUID(companion_id),
            mode=body.mode,
            domain_overrides=body.domain_overrides,
            expected_revision=body.expected_revision,
        )
    except governance_policy_service.GovernanceRevisionConflict as exc:
        return err("GOVERNANCE_POLICY_REVISION_CONFLICT", str(exc))
    except ValueError as exc:
        return err("GOVERNANCE_POLICY_SCOPE_MISMATCH", str(exc))
    return ok(policy)


@router.post("/companions/{companion_id}/governance-policy/rollback")
def rollback_governance_policy(companion_id: str, body: GovernancePolicyRollbackRequest):
    try:
        policy = governance_policy_service.rollback_governance_policy(
            uuid.UUID(companion_id),
            expected_revision=body.expected_revision,
        )
    except governance_policy_service.GovernanceRevisionConflict as exc:
        return err("GOVERNANCE_POLICY_REVISION_CONFLICT", str(exc))
    except ValueError as exc:
        return err("GOVERNANCE_POLICY_ROLLBACK_UNAVAILABLE", str(exc))
    return ok(policy)


@router.get("/companions/{companion_id}/memory-selection-policy")
def get_memory_selection_policy(companion_id: str):
    try:
        return ok(
            memory_selection_policy_service.get_policy(uuid.UUID(companion_id))
        )
    except ValueError as exc:
        return err("MEMORY_SELECTION_POLICY_SCOPE_MISMATCH", str(exc))


@router.put("/companions/{companion_id}/memory-selection-policy")
def update_memory_selection_policy(
    companion_id: str,
    body: MemorySelectionPolicyUpdateRequest,
):
    try:
        return ok(
            memory_selection_policy_service.update_policy(
                uuid.UUID(companion_id),
                enabled=body.enabled,
                expected_revision=body.expected_revision,
            )
        )
    except memory_selection_policy_service.PolicyRevisionConflict as exc:
        return err("MEMORY_SELECTION_POLICY_REVISION_CONFLICT", str(exc))
    except memory_selection_policy_service.PolicyReadinessBlocked as exc:
        return err("MEMORY_SELECTION_POLICY_READINESS_BLOCKED", str(exc), exc.details)
    except ValueError as exc:
        return err("MEMORY_SELECTION_POLICY_SCOPE_MISMATCH", str(exc))


@router.post("/companions/{companion_id}/memory-selection-policy/rollback")
def rollback_memory_selection_policy(
    companion_id: str,
    body: MemorySelectionPolicyRollbackRequest,
):
    try:
        return ok(
            memory_selection_policy_service.rollback_policy(
                uuid.UUID(companion_id),
                expected_revision=body.expected_revision,
            )
        )
    except memory_selection_policy_service.PolicyRevisionConflict as exc:
        return err("MEMORY_SELECTION_POLICY_REVISION_CONFLICT", str(exc))
    except ValueError as exc:
        return err("MEMORY_SELECTION_POLICY_ROLLBACK_FAILED", str(exc))


@router.get("/companions/{companion_id}/presence-timing-policy")
def get_presence_timing_policy(
    companion_id: str,
    surface: str = Query(...),
):
    try:
        return ok(
            presence_timing_policy_service.get_policy(
                uuid.UUID(companion_id),
                surface,
            )
        )
    except ValueError as exc:
        return err("PRESENCE_TIMING_POLICY_SCOPE_MISMATCH", str(exc))


@router.put("/companions/{companion_id}/presence-timing-policy")
def update_presence_timing_policy(
    companion_id: str,
    body: PresenceTimingPolicyUpdateRequest,
):
    try:
        return ok(
            presence_timing_policy_service.update_policy(
                uuid.UUID(companion_id),
                surface=body.surface,
                enabled=body.enabled,
                expected_revision=body.expected_revision,
            )
        )
    except presence_timing_policy_service.PolicyRevisionConflict as exc:
        return err("PRESENCE_TIMING_POLICY_REVISION_CONFLICT", str(exc))
    except presence_timing_policy_service.PolicyReadinessBlocked as exc:
        return err("PRESENCE_TIMING_POLICY_READINESS_BLOCKED", str(exc), exc.details)
    except ValueError as exc:
        return err("PRESENCE_TIMING_POLICY_SCOPE_MISMATCH", str(exc))


@router.post("/companions/{companion_id}/presence-timing-policy/rollback")
def rollback_presence_timing_policy(
    companion_id: str,
    body: PresenceTimingPolicyRollbackRequest,
):
    try:
        return ok(
            presence_timing_policy_service.rollback_policy(
                uuid.UUID(companion_id),
                surface=body.surface,
                expected_revision=body.expected_revision,
            )
        )
    except presence_timing_policy_service.PolicyRevisionConflict as exc:
        return err("PRESENCE_TIMING_POLICY_REVISION_CONFLICT", str(exc))
    except ValueError as exc:
        return err("PRESENCE_TIMING_POLICY_ROLLBACK_FAILED", str(exc))
