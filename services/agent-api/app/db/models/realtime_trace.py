"""Realtime compatibility realtime trace, replay, and redaction ORM models."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, MetadataMixin, TimestampMixin, UUIDMixin


class RealtimeTraceSession(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "realtime_trace_sessions"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=False
    )
    co_presence_session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("co_presence_sessions.id"), nullable=True
    )
    trace_run_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("trace_runs.id"), nullable=True)
    trace_status: Mapped[str] = mapped_column(Text, default="created")
    trace_level: Mapped[str] = mapped_column(Text, default="key_events")
    raw_capture_policy: Mapped[str] = mapped_column(Text, default="disabled")
    raw_audio_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_screen_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_video_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    redaction_required: Mapped[bool] = mapped_column(Boolean, default=True)
    retention_policy: Mapped[str] = mapped_column(Text, default="review_summary_only")
    trace_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    policy_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RealtimeTraceEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "realtime_trace_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_trace_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_trace_sessions.id"), nullable=False
    )
    realtime_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_status: Mapped[str] = mapped_column(Text, default="recorded")
    source_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_participants.id"), nullable=True
    )
    source_channel_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_session_channels.id"), nullable=True)
    event_summary: Mapped[str] = mapped_column(Text, default="")
    raw_payload_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_payload_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_payload_retention_policy: Mapped[str] = mapped_column(Text, default="ephemeral")
    event_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ParticipantEventTrace(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "participant_event_traces"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_trace_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_trace_events.id"), nullable=False)
    participant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_copresence_participants.id"), nullable=False)
    permission_action: Mapped[str] = mapped_column(Text, nullable=False)
    permission_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    review_required: Mapped[bool] = mapped_column(Boolean, default=True)
    permission_snapshot_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class SpeakerTrace(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "speaker_traces"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_trace_event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_trace_events.id"), nullable=False)
    voice_session_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companion_voice_sessions.id"), nullable=True)
    voice_turn_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("voice_turns.id"), nullable=True)
    speaker_participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_participants.id"), nullable=True
    )
    speaker_companion_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("companions.id"), nullable=True)
    speaker_trace_status: Mapped[str] = mapped_column(Text, default="queued")
    transcript_retention_policy: Mapped[str] = mapped_column(Text, default="ephemeral")
    transcript_excerpt_ephemeral: Mapped[bool] = mapped_column(Boolean, default=True)
    speaker_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class PermissionAuditEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "permission_audit_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_trace_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_trace_sessions.id"), nullable=False
    )
    realtime_trace_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_trace_events.id"), nullable=True)
    participant_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_participants.id"), nullable=True
    )
    context_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("multimodal_context_events.id"), nullable=True)
    hard_stop_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scoped_hard_stop_events.id"), nullable=True)
    audit_scope: Mapped[str] = mapped_column(Text, nullable=False)
    audit_decision: Mapped[str] = mapped_column(Text, default="review_required")
    requires_redaction_review: Mapped[bool] = mapped_column(Boolean, default=True)
    audit_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    audit_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")
    occurred_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MemoryGateTrace(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "memory_gate_traces"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_trace_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_trace_sessions.id"), nullable=False
    )
    realtime_trace_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_trace_events.id"), nullable=True)
    memory_buffer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_memory_buffers.id"), nullable=True)
    memory_candidate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memory_candidates.id"), nullable=True)
    shared_memory_candidate_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("shared_memory_candidates.id"), nullable=True)
    gate_status: Mapped[str] = mapped_column(Text, default="review_required")
    auto_write_blocked: Mapped[bool] = mapped_column(Boolean, default=True)
    gate_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    gate_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class RealtimeReplay(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "realtime_replays"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_trace_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_trace_sessions.id"), nullable=False
    )
    realtime_session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_copresence_sessions.id"), nullable=False
    )
    replay_status: Mapped[str] = mapped_column(Text, default="created")
    replay_scope: Mapped[str] = mapped_column(Text, default="key_events")
    includes_transcript_summary: Mapped[bool] = mapped_column(Boolean, default=True)
    includes_key_events: Mapped[bool] = mapped_column(Boolean, default=True)
    includes_raw_audio: Mapped[bool] = mapped_column(Boolean, default=False)
    includes_raw_screen: Mapped[bool] = mapped_column(Boolean, default=False)
    includes_raw_video: Mapped[bool] = mapped_column(Boolean, default=False)
    redaction_required: Mapped[bool] = mapped_column(Boolean, default=True)
    replay_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    replay_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class RealtimeReplaySegment(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "realtime_replay_segments"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_replay_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_replays.id"), nullable=False)
    source_trace_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_trace_events.id"), nullable=True)
    segment_type: Mapped[str] = mapped_column(Text, nullable=False)
    segment_order: Mapped[int] = mapped_column(Integer, default=0)
    segment_status: Mapped[str] = mapped_column(Text, default="recorded")
    segment_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_segment_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_segment_storage_allowed: Mapped[bool] = mapped_column(Boolean, default=False)
    redaction_required: Mapped[bool] = mapped_column(Boolean, default=True)
    segment_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


class RedactionEvent(Base, UUIDMixin, TimestampMixin, MetadataMixin):
    __tablename__ = "redaction_events"

    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    realtime_trace_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("realtime_trace_events.id"), nullable=True)
    realtime_replay_segment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("realtime_replay_segments.id"), nullable=True
    )
    context_event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("multimodal_context_events.id"), nullable=True)
    redaction_status: Mapped[str] = mapped_column(Text, default="pending")
    redaction_policy: Mapped[str] = mapped_column(Text, default="summary_only")
    audit_required: Mapped[bool] = mapped_column(Boolean, default=True)
    redaction_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    redaction_payload_json: Mapped[dict] = mapped_column(JSONB, default=dict, server_default="{}")


__all__ = [
    "RealtimeTraceSession",
    "RealtimeTraceEvent",
    "ParticipantEventTrace",
    "SpeakerTrace",
    "PermissionAuditEvent",
    "MemoryGateTrace",
    "RealtimeReplay",
    "RealtimeReplaySegment",
    "RedactionEvent",
]
