"""Realtime compatibility companion voice ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Double, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class VoiceProviderConfig(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "voice_provider_configs"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True)
    provider_scope: Mapped[str] = mapped_column(Text, default="user")
    provider_kind: Mapped[str] = mapped_column(Text, default="simulation")
    provider_status: Mapped[str] = mapped_column(Text, default="active")
    provider_name: Mapped[str] = mapped_column(Text, default="voice_simulation")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_streaming: Mapped[bool] = mapped_column(Boolean, default=False)
    stores_plaintext_secret: Mapped[bool] = mapped_column(Boolean, default=False)
    credentials_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_config_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class CompanionVoiceProfile(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_voice_profiles"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    provider_config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("voice_provider_configs.id"), nullable=True)
    profile_status: Mapped[str] = mapped_column(Text, default="active")
    voice_profile_name: Mapped[str] = mapped_column(Text, default="")
    voice_persona_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    tts_voice_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    stt_locale: Mapped[str | None] = mapped_column(Text, nullable=True)
    speaking_style_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    turn_taking_preferences_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class CompanionVoiceSession(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "companion_voice_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=False
    )
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    speaker_companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    speaker_realtime_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_participants.id"), nullable=True
    )
    voice_profile_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companion_voice_profiles.id"), nullable=True)
    stt_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("voice_provider_configs.id"), nullable=True)
    tts_provider_config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("voice_provider_configs.id"), nullable=True)
    session_status: Mapped[str] = mapped_column(Text, default="created")
    transcript_retention_policy: Mapped[str] = mapped_column(Text, default="ephemeral")
    memory_write_policy: Mapped[str] = mapped_column(Text, default="candidate_review")
    allow_multi_speaker: Mapped[bool] = mapped_column(Boolean, default=False)
    permission_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    voice_runtime_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VoiceTurn(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "voice_turns"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    voice_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companion_voice_sessions.id"), nullable=False)
    realtime_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=False
    )
    speaker_companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    speaker_realtime_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_participants.id"), nullable=True
    )
    turn_index: Mapped[int] = mapped_column(Integer, default=0)
    turn_status: Mapped[str] = mapped_column(Text, default="created")
    input_modality: Mapped[str] = mapped_column(Text, default="text")
    output_modality: Mapped[str] = mapped_column(Text, default="text")
    transcript_retention_policy: Mapped[str] = mapped_column(Text, default="ephemeral")
    memory_candidate_policy: Mapped[str] = mapped_column(Text, default="review_required")
    user_utterance_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    companion_response_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    turn_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SttEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "stt_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    voice_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companion_voice_sessions.id"), nullable=False)
    voice_turn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("voice_turns.id"), nullable=True)
    provider_config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("voice_provider_configs.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(Text, default="partial")
    event_status: Mapped[str] = mapped_column(Text, default="recorded")
    transcript_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_is_ephemeral: Mapped[bool] = mapped_column(Boolean, default=True)
    retention_policy: Mapped[str] = mapped_column(Text, default="ephemeral")
    confidence: Mapped[float | None] = mapped_column(Double, nullable=True)
    language: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TtsEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "tts_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    voice_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companion_voice_sessions.id"), nullable=False)
    voice_turn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("voice_turns.id"), nullable=True)
    provider_config_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("voice_provider_configs.id"), nullable=True)
    event_type: Mapped[str] = mapped_column(Text, default="queued")
    event_status: Mapped[str] = mapped_column(Text, default="recorded")
    text_preview: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_artifact_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_retention_policy: Mapped[str] = mapped_column(Text, default="ephemeral")
    raw_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TurnTakingEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "turn_taking_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    voice_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companion_voice_sessions.id"), nullable=False)
    voice_turn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("voice_turns.id"), nullable=True)
    current_speaker_companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True)
    selected_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_participants.id"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(Text, default="speaker_selected")
    event_status: Mapped[str] = mapped_column(Text, default="recorded")
    turn_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    decision_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VoiceInterruptionEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "voice_interruption_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    voice_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companion_voice_sessions.id"), nullable=False)
    voice_turn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("voice_turns.id"), nullable=True)
    source_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_participants.id"), nullable=True
    )
    target_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_participants.id"), nullable=True
    )
    interruption_type: Mapped[str] = mapped_column(Text, default="user_interrupt")
    interruption_status: Mapped[str] = mapped_column(Text, default="recorded")
    stops_tts: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_trace: Mapped[bool] = mapped_column(Boolean, default=True)
    interruption_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class VoicePersonaGuardRun(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "voice_persona_guard_runs"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    voice_session_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companion_voice_sessions.id"), nullable=False)
    voice_turn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("voice_turns.id"), nullable=True)
    speaker_companion_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=False)
    guard_status: Mapped[str] = mapped_column(Text, default="passed")
    drift_risk_level: Mapped[str] = mapped_column(Text, default="low")
    voice_style_consistency_score: Mapped[float] = mapped_column(Double, default=1.0)
    requires_review: Mapped[bool] = mapped_column(Boolean, default=False)
    blocks_response: Mapped[bool] = mapped_column(Boolean, default=False)
    transcript_excerpt_ephemeral: Mapped[bool] = mapped_column(Boolean, default=True)
    evidence_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    recommendation_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


__all__ = [
    "VoiceProviderConfig",
    "CompanionVoiceProfile",
    "CompanionVoiceSession",
    "VoiceTurn",
    "SttEvent",
    "TtsEvent",
    "TurnTakingEvent",
    "VoiceInterruptionEvent",
    "VoicePersonaGuardRun",
]
