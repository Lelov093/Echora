"""Realtime compatibility realtime co-presence schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RealtimeCoPresenceSessionRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    co_presence_session_id: uuid.UUID | None = None
    active_companion_id: uuid.UUID | None = None
    originating_conversation_id: uuid.UUID | None = None
    shared_scene_id: uuid.UUID | None = None
    session_title: str = ""
    session_status: str
    session_source: str
    default_transport: str
    permission_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    participant_summary_json: dict[str, Any] = Field(default_factory=dict)
    boundary_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    runtime_state_json: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    paused_at: datetime | None = None
    ended_at: datetime | None = None
    last_event_at: datetime | None = None

    model_config = {"from_attributes": True}


class RealtimeCoPresenceParticipantRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_session_id: uuid.UUID
    co_presence_participant_id: uuid.UUID | None = None
    participant_type: str
    participant_role: str
    participant_status: str
    participant_user_id: uuid.UUID | None = None
    participant_companion_id: uuid.UUID | None = None
    external_agent_label: str | None = None
    can_listen: bool = False
    can_speak: bool = False
    can_observe: bool = True
    can_remember: bool = False
    can_receive_transcript: bool = False
    permission_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    runtime_state_json: dict[str, Any] = Field(default_factory=dict)
    joined_at: datetime | None = None
    left_at: datetime | None = None

    model_config = {"from_attributes": True}


class RealtimeParticipantStateRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_session_id: uuid.UUID
    realtime_participant_id: uuid.UUID
    state_type: str
    state_status: str
    is_current: bool = True
    can_listen: bool = False
    can_speak: bool = False
    can_observe: bool = True
    can_remember: bool = False
    state_json: dict[str, Any] = Field(default_factory=dict)
    permission_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    recorded_at: datetime | None = None

    model_config = {"from_attributes": True}


class RealtimeSessionChannelRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_session_id: uuid.UUID
    channel_type: str
    channel_status: str
    transport_type: str
    is_default_event_stream: bool = True
    can_send_events: bool = True
    can_receive_actions: bool = False
    permission_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    runtime_state_json: dict[str, Any] = Field(default_factory=dict)
    opened_at: datetime | None = None
    closed_at: datetime | None = None
    last_event_at: datetime | None = None

    model_config = {"from_attributes": True}


class RealtimeSessionStateEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_session_id: uuid.UUID
    actor_participant_id: uuid.UUID | None = None
    event_type: str
    event_status: str
    previous_status: str | None = None
    next_status: str | None = None
    event_payload_json: dict[str, Any] = Field(default_factory=dict)
    permission_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None

    model_config = {"from_attributes": True}


class RealtimeChannelStateEventRead(RealtimeSessionStateEventRead):
    channel_id: uuid.UUID


class RealtimeCoPresenceSessionCreate(BaseModel):
    co_presence_session_id: uuid.UUID | None = None
    active_companion_id: uuid.UUID | None = None
    originating_conversation_id: uuid.UUID | None = None
    shared_scene_id: uuid.UUID | None = None
    session_title: str = ""
    session_source: str = "conversation"
    default_transport: str = "sse"
    permission_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    boundary_snapshot_json: dict[str, Any] = Field(default_factory=dict)


class RealtimeCoPresenceSessionPatch(BaseModel):
    session_title: str | None = None
    session_status: str | None = None
    paused_at: datetime | None = None
    ended_at: datetime | None = None
    runtime_state_json: dict[str, Any] | None = None


class RealtimeCoPresenceParticipantCreate(BaseModel):
    co_presence_participant_id: uuid.UUID | None = None
    participant_type: str
    participant_role: str = "listener_companion"
    participant_user_id: uuid.UUID | None = None
    participant_companion_id: uuid.UUID | None = None
    external_agent_label: str | None = None
    can_listen: bool = False
    can_speak: bool = False
    can_observe: bool = True
    can_remember: bool = False
    can_receive_transcript: bool = False
    permission_snapshot_json: dict[str, Any] = Field(default_factory=dict)


class RealtimeCoPresenceParticipantPatch(BaseModel):
    participant_role: str | None = None
    participant_status: str | None = None
    can_listen: bool | None = None
    can_speak: bool | None = None
    can_observe: bool | None = None
    can_remember: bool | None = None
    can_receive_transcript: bool | None = None
    runtime_state_json: dict[str, Any] | None = None
    left_at: datetime | None = None


class RealtimeSessionChannelPatch(BaseModel):
    channel_status: str | None = None
    can_send_events: bool | None = None
    can_receive_actions: bool | None = None
    runtime_state_json: dict[str, Any] | None = None
    closed_at: datetime | None = None
