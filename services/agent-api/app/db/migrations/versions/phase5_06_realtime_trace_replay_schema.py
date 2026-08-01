"""phase5_06_realtime_trace_replay_schema

Revision ID: p5_06_realtime_trace
Revises: p5_05_resident_presence
Create Date: 2026-06-02 00:00:00.000000

Create Phase 5 Reoriented realtime trace, replay, redaction, permission audit,
and memory gate trace schema. R6 is schema-only: no Trace UI, Replay UI, raw
audio/screen/video default storage, API implementation, service logic, or
frontend implementation.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p5_06_realtime_trace"
down_revision: Union[str, Sequence[str], None] = "p5_05_resident_presence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TRACE_STATUS_VALUES = ("created", "recording", "paused", "completed", "archived")
TRACE_LEVEL_VALUES = ("key_events", "summary", "debug")
RAW_CAPTURE_POLICY_VALUES = ("disabled", "redacted_summary", "explicit_user_authorization")
TRACE_EVENT_TYPE_VALUES = (
    "session_state",
    "channel_state",
    "participant_permission",
    "speaker_turn",
    "memory_gate",
    "redaction",
    "hard_stop",
)
TRACE_EVENT_STATUS_VALUES = ("recorded", "redacted", "suppressed", "archived")
PARTICIPANT_TRACE_ACTION_VALUES = ("listen", "speak", "observe", "remember", "receive_transcript")
SPEAKER_TRACE_STATUS_VALUES = ("queued", "speaking", "completed", "interrupted", "redacted")
PERMISSION_AUDIT_SCOPE_VALUES = ("participant", "context", "memory", "channel", "hard_stop")
PERMISSION_AUDIT_DECISION_VALUES = ("allowed", "denied", "review_required", "redacted")
MEMORY_GATE_STATUS_VALUES = ("candidate_allowed", "review_required", "blocked", "redacted")
REPLAY_STATUS_VALUES = ("created", "ready", "redacted", "archived")
REPLAY_SCOPE_VALUES = ("transcript_summary", "key_events", "permission_audit", "memory_gate")
REPLAY_SEGMENT_TYPE_VALUES = ("summary", "transcript_excerpt", "key_event", "permission_audit", "memory_gate")
REDACTION_STATUS_VALUES = ("pending", "applied", "review_required", "failed")
REDACTION_POLICY_VALUES = ("remove_raw", "mask_sensitive", "summary_only")
RETENTION_POLICY_VALUES = ("ephemeral", "review_summary_only", "explicit_retention")


def ck(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=name)


def jsonb_default() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "realtime_trace_sessions",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=True),
        sa.Column("trace_run_id", postgresql.UUID, nullable=True),
        sa.Column("trace_status", sa.Text(), nullable=False, server_default=sa.text("'created'")),
        sa.Column("trace_level", sa.Text(), nullable=False, server_default=sa.text("'key_events'")),
        sa.Column("raw_capture_policy", sa.Text(), nullable=False, server_default=sa.text("'disabled'")),
        sa.Column("raw_audio_storage_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("raw_screen_storage_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("raw_video_storage_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("redaction_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("retention_policy", sa.Text(), nullable=False, server_default=sa.text("'review_summary_only'")),
        sa.Column("trace_summary", sa.Text(), nullable=True),
        sa.Column("policy_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["trace_run_id"], ["trace_runs.id"]),
        ck("trace_status", TRACE_STATUS_VALUES, "ck_rts_trace_status"),
        ck("trace_level", TRACE_LEVEL_VALUES, "ck_rts_trace_level"),
        ck("raw_capture_policy", RAW_CAPTURE_POLICY_VALUES, "ck_rts_raw_policy"),
        ck("retention_policy", RETENTION_POLICY_VALUES, "ck_rts_retention"),
        sa.CheckConstraint(
            "raw_capture_policy = 'explicit_user_authorization' OR "
            "(raw_audio_storage_allowed = false AND raw_screen_storage_allowed = false AND raw_video_storage_allowed = false)",
            name="ck_rts_no_raw_without_auth",
        ),
        sa.CheckConstraint("redaction_required = true", name="ck_rts_redaction_required"),
    )
    op.create_index("idx_rts_realtime_status", "realtime_trace_sessions", ["realtime_session_id", "trace_status"])
    op.create_index("idx_rts_trace_run", "realtime_trace_sessions", ["trace_run_id"])

    op.create_table(
        "realtime_trace_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_trace_session_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("event_status", sa.Text(), nullable=False, server_default=sa.text("'recorded'")),
        sa.Column("source_participant_id", postgresql.UUID, nullable=True),
        sa.Column("source_channel_id", postgresql.UUID, nullable=True),
        sa.Column("event_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("raw_payload_ref", sa.Text(), nullable=True),
        sa.Column("raw_payload_storage_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("raw_payload_retention_policy", sa.Text(), nullable=False, server_default=sa.text("'ephemeral'")),
        sa.Column("event_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_trace_session_id"], ["realtime_trace_sessions.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["source_participant_id"], ["realtime_copresence_participants.id"]),
        sa.ForeignKeyConstraint(["source_channel_id"], ["realtime_session_channels.id"]),
        ck("event_type", TRACE_EVENT_TYPE_VALUES, "ck_rte_type"),
        ck("event_status", TRACE_EVENT_STATUS_VALUES, "ck_rte_status"),
        ck("raw_payload_retention_policy", RETENTION_POLICY_VALUES, "ck_rte_retention"),
        sa.CheckConstraint(
            "raw_payload_ref IS NULL OR raw_payload_storage_allowed = true",
            name="ck_rte_raw_ref_requires_storage",
        ),
        sa.CheckConstraint(
            "raw_payload_retention_policy <> 'explicit_retention' OR raw_payload_storage_allowed = true",
            name="ck_rte_explicit_retention_storage",
        ),
    )
    op.create_index("idx_rte_trace_type", "realtime_trace_events", ["realtime_trace_session_id", "event_type", "occurred_at"])
    op.create_index("idx_rte_realtime_status", "realtime_trace_events", ["realtime_session_id", "event_status"])

    op.create_table(
        "participant_event_traces",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_trace_event_id", postgresql.UUID, nullable=False),
        sa.Column("participant_id", postgresql.UUID, nullable=False),
        sa.Column("permission_action", sa.Text(), nullable=False),
        sa.Column("permission_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("permission_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_trace_event_id"], ["realtime_trace_events.id"]),
        sa.ForeignKeyConstraint(["participant_id"], ["realtime_copresence_participants.id"]),
        ck("permission_action", PARTICIPANT_TRACE_ACTION_VALUES, "ck_pet_action"),
        sa.CheckConstraint("permission_allowed = false OR review_required = true", name="ck_pet_allowed_reviewed"),
    )
    op.create_index("idx_pet_event_participant", "participant_event_traces", ["realtime_trace_event_id", "participant_id"])

    op.create_table(
        "speaker_traces",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_trace_event_id", postgresql.UUID, nullable=False),
        sa.Column("voice_session_id", postgresql.UUID, nullable=True),
        sa.Column("voice_turn_id", postgresql.UUID, nullable=True),
        sa.Column("speaker_participant_id", postgresql.UUID, nullable=True),
        sa.Column("speaker_companion_id", postgresql.UUID, nullable=True),
        sa.Column("speaker_trace_status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("transcript_retention_policy", sa.Text(), nullable=False, server_default=sa.text("'ephemeral'")),
        sa.Column("transcript_excerpt_ephemeral", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("speaker_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_trace_event_id"], ["realtime_trace_events.id"]),
        sa.ForeignKeyConstraint(["voice_session_id"], ["companion_voice_sessions.id"]),
        sa.ForeignKeyConstraint(["voice_turn_id"], ["voice_turns.id"]),
        sa.ForeignKeyConstraint(["speaker_participant_id"], ["realtime_copresence_participants.id"]),
        sa.ForeignKeyConstraint(["speaker_companion_id"], ["companions.id"]),
        ck("speaker_trace_status", SPEAKER_TRACE_STATUS_VALUES, "ck_st_status"),
        ck("transcript_retention_policy", RETENTION_POLICY_VALUES, "ck_st_retention"),
        sa.CheckConstraint(
            "transcript_retention_policy <> 'ephemeral' OR transcript_excerpt_ephemeral = true",
            name="ck_st_ephemeral_excerpt",
        ),
    )
    op.create_index("idx_st_event_status", "speaker_traces", ["realtime_trace_event_id", "speaker_trace_status"])

    op.create_table(
        "permission_audit_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_trace_session_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_trace_event_id", postgresql.UUID, nullable=True),
        sa.Column("participant_id", postgresql.UUID, nullable=True),
        sa.Column("context_event_id", postgresql.UUID, nullable=True),
        sa.Column("hard_stop_event_id", postgresql.UUID, nullable=True),
        sa.Column("audit_scope", sa.Text(), nullable=False),
        sa.Column("audit_decision", sa.Text(), nullable=False, server_default=sa.text("'review_required'")),
        sa.Column("requires_redaction_review", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("audit_summary", sa.Text(), nullable=True),
        sa.Column("audit_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_trace_session_id"], ["realtime_trace_sessions.id"]),
        sa.ForeignKeyConstraint(["realtime_trace_event_id"], ["realtime_trace_events.id"]),
        sa.ForeignKeyConstraint(["participant_id"], ["realtime_copresence_participants.id"]),
        sa.ForeignKeyConstraint(["context_event_id"], ["multimodal_context_events.id"]),
        sa.ForeignKeyConstraint(["hard_stop_event_id"], ["scoped_hard_stop_events.id"]),
        ck("audit_scope", PERMISSION_AUDIT_SCOPE_VALUES, "ck_pae_scope"),
        ck("audit_decision", PERMISSION_AUDIT_DECISION_VALUES, "ck_pae_decision"),
        sa.CheckConstraint("requires_redaction_review = true", name="ck_pae_redaction_review"),
    )
    op.create_index("idx_pae_trace_scope", "permission_audit_events", ["realtime_trace_session_id", "audit_scope", "occurred_at"])

    op.create_table(
        "memory_gate_traces",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_trace_session_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_trace_event_id", postgresql.UUID, nullable=True),
        sa.Column("memory_buffer_id", postgresql.UUID, nullable=True),
        sa.Column("memory_candidate_id", postgresql.UUID, nullable=True),
        sa.Column("shared_memory_candidate_id", postgresql.UUID, nullable=True),
        sa.Column("gate_status", sa.Text(), nullable=False, server_default=sa.text("'review_required'")),
        sa.Column("auto_write_blocked", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("gate_summary", sa.Text(), nullable=True),
        sa.Column("gate_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_trace_session_id"], ["realtime_trace_sessions.id"]),
        sa.ForeignKeyConstraint(["realtime_trace_event_id"], ["realtime_trace_events.id"]),
        sa.ForeignKeyConstraint(["memory_buffer_id"], ["realtime_memory_buffers.id"]),
        sa.ForeignKeyConstraint(["memory_candidate_id"], ["memory_candidates.id"]),
        sa.ForeignKeyConstraint(["shared_memory_candidate_id"], ["realtime_shared_memory_candidates.id"]),
        ck("gate_status", MEMORY_GATE_STATUS_VALUES, "ck_mgt_status"),
        sa.CheckConstraint("auto_write_blocked = true", name="ck_mgt_auto_write_blocked"),
    )
    op.create_index("idx_mgt_trace_status", "memory_gate_traces", ["realtime_trace_session_id", "gate_status"])

    op.create_table(
        "realtime_replays",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_trace_session_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=False),
        sa.Column("replay_status", sa.Text(), nullable=False, server_default=sa.text("'created'")),
        sa.Column("replay_scope", sa.Text(), nullable=False, server_default=sa.text("'key_events'")),
        sa.Column("includes_transcript_summary", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("includes_key_events", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("includes_raw_audio", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("includes_raw_screen", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("includes_raw_video", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("redaction_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("replay_summary", sa.Text(), nullable=True),
        sa.Column("replay_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_trace_session_id"], ["realtime_trace_sessions.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        ck("replay_status", REPLAY_STATUS_VALUES, "ck_rr_status"),
        ck("replay_scope", REPLAY_SCOPE_VALUES, "ck_rr_scope"),
        sa.CheckConstraint(
            "includes_raw_audio = false AND includes_raw_screen = false AND includes_raw_video = false",
            name="ck_rr_no_raw_default",
        ),
        sa.CheckConstraint("redaction_required = true", name="ck_rr_redaction_required"),
    )
    op.create_index("idx_rr_trace_status", "realtime_replays", ["realtime_trace_session_id", "replay_status"])

    op.create_table(
        "realtime_replay_segments",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_replay_id", postgresql.UUID, nullable=False),
        sa.Column("source_trace_event_id", postgresql.UUID, nullable=True),
        sa.Column("segment_type", sa.Text(), nullable=False),
        sa.Column("segment_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("segment_status", sa.Text(), nullable=False, server_default=sa.text("'created'")),
        sa.Column("segment_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("raw_segment_ref", sa.Text(), nullable=True),
        sa.Column("raw_segment_storage_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("redaction_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("segment_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_replay_id"], ["realtime_replays.id"]),
        sa.ForeignKeyConstraint(["source_trace_event_id"], ["realtime_trace_events.id"]),
        ck("segment_type", REPLAY_SEGMENT_TYPE_VALUES, "ck_rrs_type"),
        ck("segment_status", REPLAY_STATUS_VALUES, "ck_rrs_status"),
        sa.CheckConstraint("segment_order >= 0", name="ck_rrs_order"),
        sa.CheckConstraint("raw_segment_ref IS NULL OR raw_segment_storage_allowed = true", name="ck_rrs_raw_ref_requires_storage"),
        sa.CheckConstraint("redaction_required = true", name="ck_rrs_redaction_required"),
    )
    op.create_index("idx_rrs_replay_order", "realtime_replay_segments", ["realtime_replay_id", "segment_order"])

    op.create_table(
        "redaction_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_trace_event_id", postgresql.UUID, nullable=True),
        sa.Column("realtime_replay_segment_id", postgresql.UUID, nullable=True),
        sa.Column("context_event_id", postgresql.UUID, nullable=True),
        sa.Column("redaction_status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("redaction_policy", sa.Text(), nullable=False, server_default=sa.text("'summary_only'")),
        sa.Column("audit_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("redaction_summary", sa.Text(), nullable=True),
        sa.Column("redaction_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_trace_event_id"], ["realtime_trace_events.id"]),
        sa.ForeignKeyConstraint(["realtime_replay_segment_id"], ["realtime_replay_segments.id"]),
        sa.ForeignKeyConstraint(["context_event_id"], ["multimodal_context_events.id"]),
        ck("redaction_status", REDACTION_STATUS_VALUES, "ck_re_status"),
        ck("redaction_policy", REDACTION_POLICY_VALUES, "ck_re_policy"),
        sa.CheckConstraint(
            "realtime_trace_event_id IS NOT NULL OR realtime_replay_segment_id IS NOT NULL OR context_event_id IS NOT NULL",
            name="ck_re_target",
        ),
        sa.CheckConstraint("audit_required = true", name="ck_re_audit_required"),
    )
    op.create_index("idx_re_trace_status", "redaction_events", ["realtime_trace_event_id", "redaction_status"])
    op.create_index("idx_re_segment_status", "redaction_events", ["realtime_replay_segment_id", "redaction_status"])

    op.add_column("trace_runs", sa.Column("realtime_session_id", postgresql.UUID, nullable=True))
    op.add_column("trace_runs", sa.Column("realtime_trace_session_id", postgresql.UUID, nullable=True))
    op.create_foreign_key("fk_trace_runs_realtime_session_id", "trace_runs", "realtime_copresence_sessions", ["realtime_session_id"], ["id"])
    op.create_foreign_key(
        "fk_trace_runs_realtime_trace_session_id",
        "trace_runs",
        "realtime_trace_sessions",
        ["realtime_trace_session_id"],
        ["id"],
    )
    op.create_index("idx_trace_runs_realtime_session", "trace_runs", ["realtime_session_id"])
    op.create_index("idx_trace_runs_realtime_trace_session", "trace_runs", ["realtime_trace_session_id"])

    op.add_column("trace_steps", sa.Column("realtime_copresence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()))
    op.add_column("trace_steps", sa.Column("participant_permission_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()))
    op.add_column("trace_steps", sa.Column("realtime_memory_gate_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()))


def downgrade() -> None:
    op.drop_column("trace_steps", "realtime_memory_gate_json")
    op.drop_column("trace_steps", "participant_permission_json")
    op.drop_column("trace_steps", "realtime_copresence_json")

    op.drop_index("idx_trace_runs_realtime_trace_session", table_name="trace_runs")
    op.drop_index("idx_trace_runs_realtime_session", table_name="trace_runs")
    op.drop_constraint("fk_trace_runs_realtime_trace_session_id", "trace_runs", type_="foreignkey")
    op.drop_constraint("fk_trace_runs_realtime_session_id", "trace_runs", type_="foreignkey")
    op.drop_column("trace_runs", "realtime_trace_session_id")
    op.drop_column("trace_runs", "realtime_session_id")

    op.drop_index("idx_re_segment_status", table_name="redaction_events")
    op.drop_index("idx_re_trace_status", table_name="redaction_events")
    op.drop_table("redaction_events")

    op.drop_index("idx_rrs_replay_order", table_name="realtime_replay_segments")
    op.drop_table("realtime_replay_segments")

    op.drop_index("idx_rr_trace_status", table_name="realtime_replays")
    op.drop_table("realtime_replays")

    op.drop_index("idx_mgt_trace_status", table_name="memory_gate_traces")
    op.drop_table("memory_gate_traces")

    op.drop_index("idx_pae_trace_scope", table_name="permission_audit_events")
    op.drop_table("permission_audit_events")

    op.drop_index("idx_st_event_status", table_name="speaker_traces")
    op.drop_table("speaker_traces")

    op.drop_index("idx_pet_event_participant", table_name="participant_event_traces")
    op.drop_table("participant_event_traces")

    op.drop_index("idx_rte_realtime_status", table_name="realtime_trace_events")
    op.drop_index("idx_rte_trace_type", table_name="realtime_trace_events")
    op.drop_table("realtime_trace_events")

    op.drop_index("idx_rts_trace_run", table_name="realtime_trace_sessions")
    op.drop_index("idx_rts_realtime_status", table_name="realtime_trace_sessions")
    op.drop_table("realtime_trace_sessions")
