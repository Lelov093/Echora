"""Realtime compatibility companion voice schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class VoiceProviderConfigRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID | None = None
    provider_scope: str
    provider_kind: str
    provider_status: str
    provider_name: str
    is_default: bool = False
    supports_streaming: bool = False
    stores_plaintext_secret: bool = False
    credentials_ref: str | None = None
    provider_config_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class CompanionVoiceProfileRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    companion_id: uuid.UUID
    provider_config_id: uuid.UUID | None = None
    profile_status: str
    voice_profile_name: str
    voice_persona_summary: str | None = None
    tts_voice_key: str | None = None
    stt_locale: str | None = None
    speaking_style_json: dict[str, Any] = Field(default_factory=dict)
    turn_taking_preferences_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class CompanionVoiceSessionRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    realtime_session_id: uuid.UUID
    co_presence_session_id: uuid.UUID | None = None
    speaker_companion_id: uuid.UUID
    speaker_realtime_participant_id: uuid.UUID | None = None
    voice_profile_id: uuid.UUID | None = None
    stt_provider_config_id: uuid.UUID | None = None
    tts_provider_config_id: uuid.UUID | None = None
    session_status: str
    transcript_retention_policy: str
    memory_write_policy: str
    allow_multi_speaker: bool = False
    permission_snapshot_json: dict[str, Any] = Field(default_factory=dict)
    voice_runtime_json: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    ended_at: datetime | None = None

    model_config = {"from_attributes": True}


class VoiceTurnRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    voice_session_id: uuid.UUID
    realtime_session_id: uuid.UUID
    speaker_companion_id: uuid.UUID
    speaker_realtime_participant_id: uuid.UUID | None = None
    turn_index: int
    turn_status: str
    input_modality: str
    output_modality: str
    transcript_retention_policy: str
    memory_candidate_policy: str
    user_utterance_preview: str | None = None
    companion_response_preview: str | None = None
    turn_payload_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class SttEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    voice_session_id: uuid.UUID
    voice_turn_id: uuid.UUID | None = None
    provider_config_id: uuid.UUID | None = None
    event_type: str
    event_status: str
    transcript_text: str | None = None
    transcript_is_ephemeral: bool = True
    retention_policy: str
    confidence: float | None = None
    language: str | None = None
    raw_payload_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class TtsEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    voice_session_id: uuid.UUID
    voice_turn_id: uuid.UUID | None = None
    provider_config_id: uuid.UUID | None = None
    event_type: str
    event_status: str
    text_preview: str | None = None
    audio_artifact_ref: str | None = None
    audio_retention_policy: str
    raw_payload_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class TurnTakingEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    voice_session_id: uuid.UUID
    voice_turn_id: uuid.UUID | None = None
    current_speaker_companion_id: uuid.UUID | None = None
    selected_participant_id: uuid.UUID | None = None
    event_type: str
    event_status: str
    turn_index: int | None = None
    decision_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class VoiceInterruptionEventRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    voice_session_id: uuid.UUID
    voice_turn_id: uuid.UUID | None = None
    source_participant_id: uuid.UUID | None = None
    target_participant_id: uuid.UUID | None = None
    interruption_type: str
    interruption_status: str
    stops_tts: bool = True
    requires_trace: bool = True
    interruption_payload_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class VoicePersonaGuardRunRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    voice_session_id: uuid.UUID
    voice_turn_id: uuid.UUID | None = None
    speaker_companion_id: uuid.UUID
    guard_status: str
    drift_risk_level: str
    voice_style_consistency_score: float
    requires_review: bool = False
    blocks_response: bool = False
    transcript_excerpt_ephemeral: bool = True
    evidence_json: dict[str, Any] = Field(default_factory=dict)
    recommendation_json: dict[str, Any] = Field(default_factory=dict)

    model_config = {"from_attributes": True}


class CompanionVoiceSessionCreate(BaseModel):
    realtime_session_id: uuid.UUID
    speaker_companion_id: uuid.UUID
    speaker_realtime_participant_id: uuid.UUID | None = None
    voice_profile_id: uuid.UUID | None = None
    transcript_retention_policy: str = "ephemeral"
    memory_write_policy: str = "candidate_review"
