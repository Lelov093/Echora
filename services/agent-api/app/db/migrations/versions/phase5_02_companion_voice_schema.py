"""phase5_02_companion_voice_schema

Revision ID: p5_02_companion_voice
Revises: p5_01_realtime_copresence
Create Date: 2026-06-02 00:00:00.000000

Create Phase 5 Reoriented companion voice, STT/TTS, turn-taking,
interruption, and voice persona guard schema. R2 is schema-only: no real
provider calls, API, service, frontend, media server, WebRTC, or LiveKit.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p5_02_companion_voice"
down_revision: Union[str, Sequence[str], None] = "p5_01_realtime_copresence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PROVIDER_SCOPE_VALUES = ("stt", "tts", "combined")
PROVIDER_KIND_VALUES = ("mock", "provider_adapter")
PROVIDER_STATUS_VALUES = ("active", "disabled", "archived")

VOICE_PROFILE_STATUS_VALUES = ("active", "disabled", "archived")
VOICE_SESSION_STATUS_VALUES = ("created", "active", "paused", "ended", "archived")
TRANSCRIPT_RETENTION_VALUES = ("ephemeral", "review_summary_only", "explicit_retention")
VOICE_MEMORY_POLICY_VALUES = ("none", "candidate_review", "explicit_user_authorization")

VOICE_TURN_STATUS_VALUES = ("created", "listening", "processing", "speaking", "completed", "interrupted", "cancelled")
VOICE_INPUT_MODALITY_VALUES = ("voice", "text", "system")
VOICE_OUTPUT_MODALITY_VALUES = ("voice", "text", "silent")

STT_EVENT_TYPE_VALUES = ("partial", "final", "error")
TTS_EVENT_TYPE_VALUES = ("queued", "started", "delta", "completed", "error")
VOICE_EVENT_STATUS_VALUES = ("recorded", "applied", "rejected", "redacted")

TURN_TAKING_EVENT_TYPE_VALUES = (
    "listening_started",
    "speaker_selected",
    "speech_detected",
    "turn_locked",
    "turn_released",
    "turn_completed",
)
INTERRUPTION_TYPE_VALUES = ("user_interrupt", "hard_stop", "companion_interrupt", "timeout")
INTERRUPTION_STATUS_VALUES = ("recorded", "applied", "rejected")

VOICE_GUARD_STATUS_VALUES = ("pending", "passed", "review_required", "blocked", "overridden")
VOICE_DRIFT_RISK_VALUES = ("low", "medium", "high", "critical")


def ck(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=name)


def jsonb_default() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "voice_provider_configs",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=True),
        sa.Column("provider_scope", sa.Text(), nullable=False, server_default=sa.text("'combined'")),
        sa.Column("provider_kind", sa.Text(), nullable=False, server_default=sa.text("'mock'")),
        sa.Column("provider_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("provider_name", sa.Text(), nullable=False, server_default=sa.text("'mock'")),
        sa.Column("model_name", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("supports_streaming", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("stores_plaintext_secret", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("credentials_ref", sa.Text(), nullable=True),
        sa.Column("provider_config_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        ck("provider_scope", PROVIDER_SCOPE_VALUES, "ck_vpc_scope"),
        ck("provider_kind", PROVIDER_KIND_VALUES, "ck_vpc_kind"),
        ck("provider_status", PROVIDER_STATUS_VALUES, "ck_vpc_status"),
        sa.CheckConstraint("stores_plaintext_secret = false", name="ck_vpc_no_plaintext_secret"),
    )
    op.create_index("idx_vpc_user_scope_status", "voice_provider_configs", ["user_id", "provider_scope", "provider_status"])
    op.create_index("idx_vpc_companion_default", "voice_provider_configs", ["companion_id", "is_default"])

    op.create_table(
        "companion_voice_profiles",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("provider_config_id", postgresql.UUID, nullable=True),
        sa.Column("profile_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("voice_profile_name", sa.Text(), nullable=False, server_default=sa.text("'default'")),
        sa.Column("voice_persona_summary", sa.Text(), nullable=True),
        sa.Column("tts_voice_key", sa.Text(), nullable=True),
        sa.Column("stt_locale", sa.Text(), nullable=False, server_default=sa.text("'auto'")),
        sa.Column("speaking_style_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("turn_taking_preferences_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["provider_config_id"], ["voice_provider_configs.id"]),
        ck("profile_status", VOICE_PROFILE_STATUS_VALUES, "ck_cvp_voice_status"),
    )
    op.create_index(
        "idx_cvp_voice_companion_status",
        "companion_voice_profiles",
        ["companion_id", "profile_status", "created_at"],
    )

    op.create_table(
        "companion_voice_sessions",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=True),
        sa.Column("speaker_companion_id", postgresql.UUID, nullable=False),
        sa.Column("speaker_realtime_participant_id", postgresql.UUID, nullable=True),
        sa.Column("voice_profile_id", postgresql.UUID, nullable=True),
        sa.Column("stt_provider_config_id", postgresql.UUID, nullable=True),
        sa.Column("tts_provider_config_id", postgresql.UUID, nullable=True),
        sa.Column("session_status", sa.Text(), nullable=False, server_default=sa.text("'created'")),
        sa.Column("transcript_retention_policy", sa.Text(), nullable=False, server_default=sa.text("'ephemeral'")),
        sa.Column("memory_write_policy", sa.Text(), nullable=False, server_default=sa.text("'candidate_review'")),
        sa.Column("allow_multi_speaker", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("session_summary", sa.Text(), nullable=True),
        sa.Column("permission_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("voice_runtime_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["speaker_companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["speaker_realtime_participant_id"], ["realtime_copresence_participants.id"]),
        sa.ForeignKeyConstraint(["voice_profile_id"], ["companion_voice_profiles.id"]),
        sa.ForeignKeyConstraint(["stt_provider_config_id"], ["voice_provider_configs.id"]),
        sa.ForeignKeyConstraint(["tts_provider_config_id"], ["voice_provider_configs.id"]),
        ck("session_status", VOICE_SESSION_STATUS_VALUES, "ck_cvs_status"),
        ck("transcript_retention_policy", TRANSCRIPT_RETENTION_VALUES, "ck_cvs_transcript_retention"),
        ck("memory_write_policy", VOICE_MEMORY_POLICY_VALUES, "ck_cvs_memory_policy"),
        sa.CheckConstraint("allow_multi_speaker = false", name="ck_cvs_single_speaker"),
    )
    op.create_index(
        "idx_cvs_realtime_status",
        "companion_voice_sessions",
        ["realtime_session_id", "session_status", "created_at"],
    )
    op.create_index(
        "idx_cvs_speaker_status",
        "companion_voice_sessions",
        ["speaker_companion_id", "session_status", "created_at"],
    )

    op.create_table(
        "voice_turns",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("voice_session_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=False),
        sa.Column("speaker_companion_id", postgresql.UUID, nullable=False),
        sa.Column("speaker_realtime_participant_id", postgresql.UUID, nullable=True),
        sa.Column("turn_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("turn_status", sa.Text(), nullable=False, server_default=sa.text("'created'")),
        sa.Column("input_modality", sa.Text(), nullable=False, server_default=sa.text("'voice'")),
        sa.Column("output_modality", sa.Text(), nullable=False, server_default=sa.text("'voice'")),
        sa.Column("transcript_retention_policy", sa.Text(), nullable=False, server_default=sa.text("'ephemeral'")),
        sa.Column("memory_candidate_policy", sa.Text(), nullable=False, server_default=sa.text("'candidate_review'")),
        sa.Column("user_utterance_preview", sa.Text(), nullable=True),
        sa.Column("companion_response_preview", sa.Text(), nullable=True),
        sa.Column("turn_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["voice_session_id"], ["companion_voice_sessions.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["speaker_companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["speaker_realtime_participant_id"], ["realtime_copresence_participants.id"]),
        ck("turn_status", VOICE_TURN_STATUS_VALUES, "ck_vt_status"),
        ck("input_modality", VOICE_INPUT_MODALITY_VALUES, "ck_vt_input"),
        ck("output_modality", VOICE_OUTPUT_MODALITY_VALUES, "ck_vt_output"),
        ck("transcript_retention_policy", TRANSCRIPT_RETENTION_VALUES, "ck_vt_transcript_retention"),
        ck("memory_candidate_policy", VOICE_MEMORY_POLICY_VALUES, "ck_vt_memory_policy"),
    )
    op.create_index("idx_vt_voice_session_turn", "voice_turns", ["voice_session_id", "turn_index"])

    op.create_table(
        "stt_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("voice_session_id", postgresql.UUID, nullable=False),
        sa.Column("voice_turn_id", postgresql.UUID, nullable=True),
        sa.Column("provider_config_id", postgresql.UUID, nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False, server_default=sa.text("'partial'")),
        sa.Column("event_status", sa.Text(), nullable=False, server_default=sa.text("'recorded'")),
        sa.Column("transcript_text", sa.Text(), nullable=True),
        sa.Column("transcript_is_ephemeral", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("retention_policy", sa.Text(), nullable=False, server_default=sa.text("'ephemeral'")),
        sa.Column("confidence", sa.Double(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["voice_session_id"], ["companion_voice_sessions.id"]),
        sa.ForeignKeyConstraint(["voice_turn_id"], ["voice_turns.id"]),
        sa.ForeignKeyConstraint(["provider_config_id"], ["voice_provider_configs.id"]),
        ck("event_type", STT_EVENT_TYPE_VALUES, "ck_stt_type"),
        ck("event_status", VOICE_EVENT_STATUS_VALUES, "ck_stt_status"),
        ck("retention_policy", TRANSCRIPT_RETENTION_VALUES, "ck_stt_retention"),
        sa.CheckConstraint(
            "(retention_policy <> 'ephemeral' OR transcript_is_ephemeral = true)",
            name="ck_stt_ephemeral_default",
        ),
    )
    op.create_index("idx_stt_voice_turn", "stt_events", ["voice_turn_id", "occurred_at"])

    op.create_table(
        "tts_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("voice_session_id", postgresql.UUID, nullable=False),
        sa.Column("voice_turn_id", postgresql.UUID, nullable=True),
        sa.Column("provider_config_id", postgresql.UUID, nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("event_status", sa.Text(), nullable=False, server_default=sa.text("'recorded'")),
        sa.Column("text_preview", sa.Text(), nullable=True),
        sa.Column("audio_artifact_ref", sa.Text(), nullable=True),
        sa.Column("audio_retention_policy", sa.Text(), nullable=False, server_default=sa.text("'ephemeral'")),
        sa.Column("raw_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["voice_session_id"], ["companion_voice_sessions.id"]),
        sa.ForeignKeyConstraint(["voice_turn_id"], ["voice_turns.id"]),
        sa.ForeignKeyConstraint(["provider_config_id"], ["voice_provider_configs.id"]),
        ck("event_type", TTS_EVENT_TYPE_VALUES, "ck_tts_type"),
        ck("event_status", VOICE_EVENT_STATUS_VALUES, "ck_tts_status"),
        ck("audio_retention_policy", TRANSCRIPT_RETENTION_VALUES, "ck_tts_audio_retention"),
    )
    op.create_index("idx_tts_voice_turn", "tts_events", ["voice_turn_id", "occurred_at"])

    op.create_table(
        "turn_taking_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("voice_session_id", postgresql.UUID, nullable=False),
        sa.Column("voice_turn_id", postgresql.UUID, nullable=True),
        sa.Column("current_speaker_companion_id", postgresql.UUID, nullable=False),
        sa.Column("selected_participant_id", postgresql.UUID, nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False, server_default=sa.text("'listening_started'")),
        sa.Column("event_status", sa.Text(), nullable=False, server_default=sa.text("'recorded'")),
        sa.Column("turn_index", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("decision_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["voice_session_id"], ["companion_voice_sessions.id"]),
        sa.ForeignKeyConstraint(["voice_turn_id"], ["voice_turns.id"]),
        sa.ForeignKeyConstraint(["current_speaker_companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["selected_participant_id"], ["realtime_copresence_participants.id"]),
        ck("event_type", TURN_TAKING_EVENT_TYPE_VALUES, "ck_tte_type"),
        ck("event_status", VOICE_EVENT_STATUS_VALUES, "ck_tte_status"),
    )
    op.create_index("idx_tte_voice_session", "turn_taking_events", ["voice_session_id", "occurred_at"])

    op.create_table(
        "voice_interruption_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("voice_session_id", postgresql.UUID, nullable=False),
        sa.Column("voice_turn_id", postgresql.UUID, nullable=True),
        sa.Column("source_participant_id", postgresql.UUID, nullable=True),
        sa.Column("target_participant_id", postgresql.UUID, nullable=True),
        sa.Column("interruption_type", sa.Text(), nullable=False, server_default=sa.text("'user_interrupt'")),
        sa.Column("interruption_status", sa.Text(), nullable=False, server_default=sa.text("'recorded'")),
        sa.Column("stops_tts", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("requires_trace", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("reason_summary", sa.Text(), nullable=True),
        sa.Column("interruption_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["voice_session_id"], ["companion_voice_sessions.id"]),
        sa.ForeignKeyConstraint(["voice_turn_id"], ["voice_turns.id"]),
        sa.ForeignKeyConstraint(["source_participant_id"], ["realtime_copresence_participants.id"]),
        sa.ForeignKeyConstraint(["target_participant_id"], ["realtime_copresence_participants.id"]),
        ck("interruption_type", INTERRUPTION_TYPE_VALUES, "ck_vie_type"),
        ck("interruption_status", INTERRUPTION_STATUS_VALUES, "ck_vie_status"),
    )
    op.create_index("idx_vie_voice_session", "voice_interruption_events", ["voice_session_id", "occurred_at"])

    op.create_table(
        "voice_persona_guard_runs",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("voice_session_id", postgresql.UUID, nullable=False),
        sa.Column("voice_turn_id", postgresql.UUID, nullable=True),
        sa.Column("speaker_companion_id", postgresql.UUID, nullable=False),
        sa.Column("guard_status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("drift_risk_level", sa.Text(), nullable=False, server_default=sa.text("'low'")),
        sa.Column("voice_style_consistency_score", sa.Double(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("requires_review", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("blocks_response", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("transcript_excerpt_ephemeral", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("guard_summary", sa.Text(), nullable=True),
        sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("recommendation_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["voice_session_id"], ["companion_voice_sessions.id"]),
        sa.ForeignKeyConstraint(["voice_turn_id"], ["voice_turns.id"]),
        sa.ForeignKeyConstraint(["speaker_companion_id"], ["companions.id"]),
        ck("guard_status", VOICE_GUARD_STATUS_VALUES, "ck_vpgr_status"),
        ck("drift_risk_level", VOICE_DRIFT_RISK_VALUES, "ck_vpgr_risk"),
        sa.CheckConstraint(
            "(drift_risk_level NOT IN ('high', 'critical') OR requires_review = true)",
            name="ck_vpgr_high_risk_review",
        ),
        sa.CheckConstraint("transcript_excerpt_ephemeral = true", name="ck_vpgr_ephemeral_excerpt"),
    )
    op.create_index("idx_vpgr_voice_session", "voice_persona_guard_runs", ["voice_session_id", "created_at"])
    op.create_index("idx_vpgr_speaker_status", "voice_persona_guard_runs", ["speaker_companion_id", "guard_status", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_vpgr_speaker_status", table_name="voice_persona_guard_runs")
    op.drop_index("idx_vpgr_voice_session", table_name="voice_persona_guard_runs")
    op.drop_table("voice_persona_guard_runs")

    op.drop_index("idx_vie_voice_session", table_name="voice_interruption_events")
    op.drop_table("voice_interruption_events")

    op.drop_index("idx_tte_voice_session", table_name="turn_taking_events")
    op.drop_table("turn_taking_events")

    op.drop_index("idx_tts_voice_turn", table_name="tts_events")
    op.drop_table("tts_events")

    op.drop_index("idx_stt_voice_turn", table_name="stt_events")
    op.drop_table("stt_events")

    op.drop_index("idx_vt_voice_session_turn", table_name="voice_turns")
    op.drop_table("voice_turns")

    op.drop_index("idx_cvs_speaker_status", table_name="companion_voice_sessions")
    op.drop_index("idx_cvs_realtime_status", table_name="companion_voice_sessions")
    op.drop_table("companion_voice_sessions")

    op.drop_index("idx_cvp_voice_companion_status", table_name="companion_voice_profiles")
    op.drop_table("companion_voice_profiles")

    op.drop_index("idx_vpc_companion_default", table_name="voice_provider_configs")
    op.drop_index("idx_vpc_user_scope_status", table_name="voice_provider_configs")
    op.drop_table("voice_provider_configs")
