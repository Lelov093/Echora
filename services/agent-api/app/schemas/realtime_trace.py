"""Realtime compatibility realtime trace, replay, and redaction schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RealtimeTraceSessionRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_session_id: uuid.UUID
    co_presence_session_id: uuid.UUID | None = None
    trace_run_id: uuid.UUID | None = None
    trace_status: str
    trace_level: str
    raw_capture_policy: str
    raw_audio_storage_allowed: bool = False
    raw_screen_storage_allowed: bool = False
    raw_video_storage_allowed: bool = False
    redaction_required: bool = True
    retention_policy: str
    trace_summary: str | None = None
    policy_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    ended_at: datetime | None = None

    model_config = {"from_attributes": True}


class RealtimeTraceEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_trace_session_id: uuid.UUID
    realtime_session_id: uuid.UUID
    event_type: str
    event_status: str
    source_participant_id: uuid.UUID | None = None
    source_channel_id: uuid.UUID | None = None
    event_summary: str
    raw_payload_ref: str | None = None
    raw_payload_storage_allowed: bool = False
    raw_payload_retention_policy: str
    event_payload_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class ParticipantEventTraceRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_trace_event_id: uuid.UUID
    participant_id: uuid.UUID
    permission_action: str
    permission_allowed: bool = False
    review_required: bool = True
    permission_snapshot_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class SpeakerTraceRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_trace_event_id: uuid.UUID
    voice_session_id: uuid.UUID | None = None
    voice_turn_id: uuid.UUID | None = None
    speaker_participant_id: uuid.UUID | None = None
    speaker_companion_id: uuid.UUID | None = None
    speaker_trace_status: str
    transcript_retention_policy: str
    transcript_excerpt_ephemeral: bool = True
    speaker_payload_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class PermissionAuditEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_trace_session_id: uuid.UUID
    realtime_trace_event_id: uuid.UUID | None = None
    participant_id: uuid.UUID | None = None
    context_event_id: uuid.UUID | None = None
    hard_stop_event_id: uuid.UUID | None = None
    audit_scope: str
    audit_decision: str
    requires_redaction_review: bool = True
    audit_summary: str | None = None
    audit_payload_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class MemoryGateTraceRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_trace_session_id: uuid.UUID
    realtime_trace_event_id: uuid.UUID | None = None
    memory_buffer_id: uuid.UUID | None = None
    memory_candidate_id: uuid.UUID | None = None
    shared_memory_candidate_id: uuid.UUID | None = None
    gate_status: str
    auto_write_blocked: bool = True
    gate_summary: str | None = None
    gate_payload_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class RealtimeReplayRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_trace_session_id: uuid.UUID
    realtime_session_id: uuid.UUID
    replay_status: str
    replay_scope: str
    includes_transcript_summary: bool = True
    includes_key_events: bool = True
    includes_raw_audio: bool = False
    includes_raw_screen: bool = False
    includes_raw_video: bool = False
    redaction_required: bool = True
    replay_summary: str | None = None
    replay_payload_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class RealtimeReplaySegmentRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_replay_id: uuid.UUID
    source_trace_event_id: uuid.UUID | None = None
    segment_type: str
    segment_order: int
    segment_status: str
    segment_summary: str | None = None
    raw_segment_ref: str | None = None
    raw_segment_storage_allowed: bool = False
    redaction_required: bool = True
    segment_payload_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class RedactionEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_trace_event_id: uuid.UUID | None = None
    realtime_replay_segment_id: uuid.UUID | None = None
    context_event_id: uuid.UUID | None = None
    redaction_status: str
    redaction_policy: str
    audit_required: bool = True
    redaction_summary: str | None = None
    redaction_payload_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class RealtimeTraceSessionCreate(BaseModel):
    realtime_session_id: uuid.UUID
    co_presence_session_id: uuid.UUID | None = None
    trace_level: str = "key_events"
    raw_capture_policy: str = "disabled"
    redaction_required: bool = True
    retention_policy: str = "review_summary_only"
