"""Reliability diagnostics and user-controlled data-rights operations."""

import uuid

from fastapi import APIRouter

from app.schemas.common import err, ok
from app.schemas.reliability import (
    CompanionDeletionCreateRequest,
    CompanionDeletionExecuteRequest,
    DataRightsDryRunRequest,
)
from app.services import (
    data_rights_deletion_service,
    data_rights_export_service,
    reliability_diagnostics_service,
)


router = APIRouter(tags=["Reliability"])


@router.get("/companions/{companion_id}/reliability-diagnostics")
def get_reliability_diagnostics(companion_id: str):
    try:
        return ok(reliability_diagnostics_service.get_reliability_diagnostics(uuid.UUID(companion_id)))
    except (ValueError, TypeError) as exc:
        return err("RELIABILITY_SCOPE_INVALID", str(exc))


@router.post("/companions/{companion_id}/data-rights/dry-run")
def dry_run_data_rights(companion_id: str, body: DataRightsDryRunRequest):
    try:
        return ok(reliability_diagnostics_service.get_data_rights_dry_run(uuid.UUID(companion_id), body.operation, body.target_id))
    except (ValueError, TypeError) as exc:
        return err("DATA_RIGHTS_DRY_RUN_REJECTED", str(exc))


@router.post("/companions/{companion_id}/data-rights/export")
def export_companion_data(companion_id: str):
    try:
        return ok(
            data_rights_export_service.export_companion_data(
                uuid.UUID(companion_id)
            )
        )
    except (ValueError, TypeError) as exc:
        return err("COMPANION_DATA_EXPORT_REJECTED", str(exc))


@router.get("/companions/{companion_id}/data-rights/deletion-request")
def get_companion_deletion_request(companion_id: str):
    try:
        return ok(
            data_rights_deletion_service.get_companion_deletion_request(
                uuid.UUID(companion_id)
            )
        )
    except (ValueError, TypeError) as exc:
        return err("COMPANION_DELETION_STATUS_REJECTED", str(exc))


@router.get("/data-rights/deletion-requests/{request_id}")
def get_deletion_request(request_id: str):
    try:
        return ok(
            data_rights_deletion_service.get_deletion_request(
                uuid.UUID(request_id)
            )
        )
    except (ValueError, TypeError) as exc:
        return err("COMPANION_DELETION_STATUS_REJECTED", str(exc))


@router.post("/companions/{companion_id}/data-rights/deletion-requests")
def create_companion_deletion_request(
    companion_id: str,
    body: CompanionDeletionCreateRequest,
):
    try:
        return ok(
            data_rights_deletion_service.create_deletion_request(
                uuid.UUID(companion_id),
                confirmation_name=body.confirmation_name,
                skip_recovery_window=body.skip_recovery_window,
                export_choice=body.export_choice,
                idempotency_key=body.idempotency_key,
            )
        )
    except (ValueError, TypeError) as exc:
        return err("COMPANION_DELETION_REJECTED", str(exc))


@router.post("/data-rights/deletion-requests/{request_id}/restore")
def restore_companion_deletion_request(request_id: str):
    try:
        return ok(
            data_rights_deletion_service.restore_deletion_request(
                uuid.UUID(request_id)
            )
        )
    except (ValueError, TypeError) as exc:
        return err("COMPANION_DELETION_RESTORE_REJECTED", str(exc))


@router.post("/data-rights/deletion-requests/{request_id}/execute")
def execute_companion_deletion_request(
    request_id: str,
    body: CompanionDeletionExecuteRequest,
):
    try:
        return ok(
            data_rights_deletion_service.execute_deletion_request(
                uuid.UUID(request_id),
                allow_before_due=body.allow_before_due,
            )
        )
    except (ValueError, TypeError) as exc:
        return err("COMPANION_DELETION_EXECUTION_REJECTED", str(exc))
