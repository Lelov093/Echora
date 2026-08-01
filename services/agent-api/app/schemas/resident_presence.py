"""Realtime compatibility resident presence and hard-stop schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CompanionResidentStatusEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    realtime_session_id: uuid.UUID | None = None
    status_type: str
    status_source: str
    interruption_level: str
    allows_unsolicited_presence: bool = False
    presence_summary: str | None = None
    policy_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class CompanionPresenceBudgetRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    budget_scope: str
    budget_status: str
    enforcement_policy: str
    max_presence_minutes: int
    used_presence_minutes: int
    max_interruptions: int
    used_interruptions: int
    window_starts_at: datetime | None = None
    window_ends_at: datetime | None = None
    budget_policy_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class CoPresenceInvitationRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    co_presence_session_id: uuid.UUID | None = None
    realtime_session_id: uuid.UUID | None = None
    inviter_companion_id: uuid.UUID | None = None
    target_companion_id: uuid.UUID
    invitation_status: str
    invitation_source: str
    requires_user_approval: bool = True
    auto_join_allowed: bool = False
    memory_candidate_allowed: bool = False
    invitation_reason: str | None = None
    policy_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    expires_at: datetime | None = None

    model_config = {"from_attributes": True}


class QuietHourSettingRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID | None = None
    quiet_status: str
    quiet_policy: str
    day_of_week: int | None = None
    start_minute: int
    end_minute: int
    timezone: str
    allows_emergency_override: bool = False
    policy_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class FocusModeEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID | None = None
    realtime_session_id: uuid.UUID | None = None
    focus_status: str
    focus_scope: str
    suppress_presence: bool = True
    suppress_notifications: bool = True
    allow_critical_only: bool = False
    reason: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None
    policy_snapshot_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class ResidentPresenceEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    realtime_session_id: uuid.UUID | None = None
    event_type: str
    event_status: str
    interruption_level: str
    requires_user_confirmation: bool = False
    delivery_surface: str
    event_summary: str | None = None
    policy_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class ScopedHardStopEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    hard_stop_scope: str
    hard_stop_status: str
    initiated_by: str
    realtime_session_id: uuid.UUID | None = None
    channel_id: uuid.UUID | None = None
    companion_id: uuid.UUID | None = None
    context_event_id: uuid.UUID | None = None
    stop_reason: str | None = None
    stops_listening: bool = True
    stops_speaking: bool = True
    stops_observing: bool = True
    stops_memory_capture: bool = True
    stops_context_capture: bool = True
    requires_audit: bool = True
    policy_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    released_at: datetime | None = None

    model_config = {"from_attributes": True}


class HardStopAuditEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    hard_stop_event_id: uuid.UUID
    audit_event_type: str
    audit_status: str
    affected_scope: str
    affected_participant_id: uuid.UUID | None = None
    audit_summary: str | None = None
    audit_payload_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class ScopedHardStopEventCreate(BaseModel):
    hard_stop_scope: str
    realtime_session_id: uuid.UUID | None = None
    channel_id: uuid.UUID | None = None
    companion_id: uuid.UUID | None = None
    context_event_id: uuid.UUID | None = None
    stop_reason: str | None = None
    requires_audit: bool = True
