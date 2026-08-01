"""Reliability and user-controlled data-rights request contracts."""

from typing import Literal

from pydantic import BaseModel, Field


DataRightsOperation = Literal[
    "export",
    "forget_memory",
    "archive_companion",
    "disconnect_channels",
    "revoke_channels",
    "permanent_delete",
]


class DataRightsDryRunRequest(BaseModel):
    operation: DataRightsOperation
    target_id: str | None = None
    reason: str | None = Field(default=None, max_length=500)


class CompanionDeletionCreateRequest(BaseModel):
    confirmation_name: str = Field(min_length=1, max_length=255)
    skip_recovery_window: bool = False
    export_choice: Literal["skip", "completed"]
    idempotency_key: str = Field(min_length=8, max_length=200)


class CompanionDeletionExecuteRequest(BaseModel):
    allow_before_due: bool = False
