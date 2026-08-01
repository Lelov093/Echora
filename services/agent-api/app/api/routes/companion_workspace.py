"""Read-only Companion workspace, chronicle and review-inbox routes."""

import uuid
from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import err, ok
from app.services import companion_workspace_service, chronicle_summary_service

router = APIRouter(prefix="/companions", tags=["Companion Workspace"])


class ChronicleRefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    correction_note: str | None = Field(default=None, max_length=500)


class ChronicleInvalidateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=500)


def _id(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(value)
    except ValueError:
        return None


@router.get("/{companion_id}/workspace")
def get_workspace(companion_id: str):
    parsed = _id(companion_id)
    if not parsed:
        return err("INVALID_COMPANION_ID", "Companion id must be a UUID")
    data = companion_workspace_service.get_workspace(parsed)
    return ok(data) if data else err("COMPANION_NOT_FOUND", "Companion not found")


@router.get("/{companion_id}/chronicle")
def get_chronicle(companion_id: str, limit: int = Query(40, ge=1, le=100), offset: int = Query(0, ge=0)):
    parsed = _id(companion_id)
    if not parsed:
        return err("INVALID_COMPANION_ID", "Companion id must be a UUID")
    data = companion_workspace_service.get_chronicle(parsed, limit, offset)
    return ok(data) if data else err("COMPANION_NOT_FOUND", "Companion not found")


@router.post("/{companion_id}/chronicle/summaries/refresh")
def refresh_chronicle_summary(companion_id: str, body: ChronicleRefreshRequest):
    parsed = _id(companion_id)
    if not parsed:
        return err("INVALID_COMPANION_ID", "Companion id must be a UUID")
    chronicle = companion_workspace_service.get_chronicle(parsed, 100, 0)
    if not chronicle:
        return err("COMPANION_NOT_FOUND", "Companion not found")
    try:
        result = chronicle_summary_service.generate_summary(parsed, chronicle["items"], body.correction_note)
    except chronicle_summary_service.ChronicleSummaryError as exc:
        return err(exc.code, exc.message)
    return ok(result)


@router.post("/{companion_id}/chronicle/summaries/{summary_id}/invalidate")
def invalidate_chronicle_summary(companion_id: str, summary_id: str, body: ChronicleInvalidateRequest):
    parsed, summary = _id(companion_id), _id(summary_id)
    if not parsed or not summary:
        return err("INVALID_ID", "Companion and summary ids must be UUIDs")
    try:
        result = chronicle_summary_service.invalidate_summary(parsed, summary, body.reason)
    except chronicle_summary_service.ChronicleSummaryError as exc:
        return err(exc.code, exc.message)
    return ok(result)


@router.get("/{companion_id}/review-inbox")
def get_review_inbox(
    companion_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    kind: Literal[
        "memory", "growth", "persona_growth", "private_to_shared",
        "shared_to_private", "cross_companion", "channel", "realtime_shared", "relationship",
    ] | None = None,
):
    parsed = _id(companion_id)
    if not parsed:
        return err("INVALID_COMPANION_ID", "Companion id must be a UUID")
    data = companion_workspace_service.get_review_inbox(parsed, limit, offset, kind)
    return ok(data) if data else err("COMPANION_NOT_FOUND", "Companion not found")
