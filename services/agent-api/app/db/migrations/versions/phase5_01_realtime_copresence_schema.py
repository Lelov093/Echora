"""phase5_01_realtime_copresence_schema

Revision ID: p5_01_realtime_copresence
Revises: p4_04_persona_growth_presence
Create Date: 2026-06-02 00:00:00.000000

Create Phase 5 Reoriented realtime co-presence session, participant,
channel, and state event schema. R1 is schema-only: no API, service,
frontend, SSE, WebSocket, WebRTC, or LiveKit implementation.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p5_01_realtime_copresence"
down_revision: Union[str, Sequence[str], None] = "p4_04_persona_growth_presence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


REALTIME_SESSION_STATUS_VALUES = ("created", "active", "paused", "ended", "archived")
REALTIME_SESSION_SOURCE_VALUES = ("co_presence_session", "conversation", "shared_scene", "manual", "test")
REALTIME_TRANSPORT_VALUES = ("sse", "rest", "internal", "mock")

REALTIME_PARTICIPANT_TYPE_VALUES = ("user", "companion", "external_agent")
REALTIME_PARTICIPANT_ROLE_VALUES = (
    "user",
    "speaker_companion",
    "listener_companion",
    "observing_companion",
    "delegated_executor",
)
REALTIME_PARTICIPANT_STATUS_VALUES = ("invited", "active", "paused", "muted", "left", "removed")

REALTIME_PARTICIPANT_STATE_TYPE_VALUES = (
    "presence",
    "voice",
    "transcript",
    "permission",
    "memory",
    "attention",
)
REALTIME_PARTICIPANT_STATE_STATUS_VALUES = ("active", "paused", "muted", "blocked", "left")

REALTIME_CHANNEL_TYPE_VALUES = ("sse", "rest_action", "voice", "transcript", "permission", "memory", "hard_stop", "trace")
REALTIME_CHANNEL_STATUS_VALUES = ("created", "active", "paused", "closed", "failed")

REALTIME_SESSION_EVENT_TYPE_VALUES = (
    "session.created",
    "session.started",
    "session.paused",
    "session.resumed",
    "session.ended",
    "participant.updated",
    "permission.changed",
    "hard_stop.triggered",
)
REALTIME_CHANNEL_EVENT_TYPE_VALUES = (
    "channel.created",
    "channel.opened",
    "channel.paused",
    "channel.resumed",
    "channel.closed",
    "channel.failed",
    "event.published",
    "permission.changed",
    "hard_stop.triggered",
)
REALTIME_EVENT_STATUS_VALUES = ("recorded", "applied", "rejected", "redacted")


def ck(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=name)


def jsonb_default() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "realtime_copresence_sessions",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=True),
        sa.Column("active_companion_id", postgresql.UUID, nullable=True),
        sa.Column("originating_conversation_id", postgresql.UUID, nullable=True),
        sa.Column("shared_scene_id", postgresql.UUID, nullable=True),
        sa.Column("session_title", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("session_summary", sa.Text(), nullable=True),
        sa.Column("session_status", sa.Text(), nullable=False, server_default=sa.text("'created'")),
        sa.Column("session_source", sa.Text(), nullable=False, server_default=sa.text("'co_presence_session'")),
        sa.Column("default_transport", sa.Text(), nullable=False, server_default=sa.text("'sse'")),
        sa.Column("permission_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("participant_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("boundary_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("runtime_state_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["active_companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["originating_conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["shared_scene_id"], ["shared_scenes.id"]),
        ck("session_status", REALTIME_SESSION_STATUS_VALUES, "ck_rtcs_status"),
        ck("session_source", REALTIME_SESSION_SOURCE_VALUES, "ck_rtcs_source"),
        ck("default_transport", REALTIME_TRANSPORT_VALUES, "ck_rtcs_transport"),
        sa.CheckConstraint(
            "(co_presence_session_id IS NOT NULL OR active_companion_id IS NOT NULL)",
            name="ck_rtcs_context_binding",
        ),
    )
    op.create_index("idx_rtcs_user_status", "realtime_copresence_sessions", ["user_id", "session_status", "created_at"])
    op.create_index(
        "idx_rtcs_co_presence_status",
        "realtime_copresence_sessions",
        ["co_presence_session_id", "session_status", "created_at"],
    )
    op.create_index(
        "idx_rtcs_active_companion_status",
        "realtime_copresence_sessions",
        ["active_companion_id", "session_status", "created_at"],
    )

    op.create_table(
        "realtime_copresence_participants",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_participant_id", postgresql.UUID, nullable=True),
        sa.Column("participant_type", sa.Text(), nullable=False),
        sa.Column("participant_role", sa.Text(), nullable=False, server_default=sa.text("'observing_companion'")),
        sa.Column("participant_status", sa.Text(), nullable=False, server_default=sa.text("'invited'")),
        sa.Column("participant_user_id", postgresql.UUID, nullable=True),
        sa.Column("participant_companion_id", postgresql.UUID, nullable=True),
        sa.Column("external_agent_label", sa.Text(), nullable=True),
        sa.Column("display_label", sa.Text(), nullable=True),
        sa.Column("can_listen", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_speak", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_observe", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("can_remember", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_receive_transcript", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("permission_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("runtime_state_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["co_presence_participant_id"], ["co_presence_participants.id"]),
        sa.ForeignKeyConstraint(["participant_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["participant_companion_id"], ["companions.id"]),
        ck("participant_type", REALTIME_PARTICIPANT_TYPE_VALUES, "ck_rtcp_type"),
        ck("participant_role", REALTIME_PARTICIPANT_ROLE_VALUES, "ck_rtcp_role"),
        ck("participant_status", REALTIME_PARTICIPANT_STATUS_VALUES, "ck_rtcp_status"),
        sa.CheckConstraint(
            "("
            "(participant_type = 'user' AND participant_user_id IS NOT NULL AND participant_companion_id IS NULL AND external_agent_label IS NULL)"
            " OR "
            "(participant_type = 'companion' AND participant_user_id IS NULL AND participant_companion_id IS NOT NULL AND external_agent_label IS NULL)"
            " OR "
            "(participant_type = 'external_agent' AND participant_user_id IS NULL AND participant_companion_id IS NULL AND NULLIF(TRIM(COALESCE(external_agent_label, '')), '') IS NOT NULL)"
            ")",
            name="ck_rtcp_subject",
        ),
        sa.CheckConstraint(
            "("
            "(participant_role = 'user' AND participant_type = 'user')"
            " OR "
            "(participant_role IN ('speaker_companion', 'listener_companion', 'observing_companion') AND participant_type = 'companion')"
            " OR "
            "(participant_role = 'delegated_executor' AND participant_type = 'external_agent')"
            ")",
            name="ck_rtcp_role_match",
        ),
        sa.CheckConstraint(
            "("
            "participant_role <> 'observing_companion' "
            "OR (can_listen = false AND can_speak = false AND can_remember = false AND can_receive_transcript = false)"
            ")",
            name="ck_rtcp_observer_boundary",
        ),
    )
    op.create_index(
        "idx_rtcp_session_role",
        "realtime_copresence_participants",
        ["realtime_session_id", "participant_role", "participant_status"],
    )
    op.create_index(
        "idx_rtcp_co_presence_participant",
        "realtime_copresence_participants",
        ["co_presence_participant_id"],
    )

    op.create_table(
        "realtime_participant_states",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_participant_id", postgresql.UUID, nullable=False),
        sa.Column("state_type", sa.Text(), nullable=False, server_default=sa.text("'presence'")),
        sa.Column("state_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("can_listen", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_speak", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_observe", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("can_remember", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("state_summary", sa.Text(), nullable=True),
        sa.Column("state_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("permission_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["realtime_participant_id"], ["realtime_copresence_participants.id"]),
        ck("state_type", REALTIME_PARTICIPANT_STATE_TYPE_VALUES, "ck_rtps_type"),
        ck("state_status", REALTIME_PARTICIPANT_STATE_STATUS_VALUES, "ck_rtps_status"),
    )
    op.create_index(
        "idx_rtps_participant_current",
        "realtime_participant_states",
        ["realtime_participant_id", "is_current", "recorded_at"],
    )

    op.create_table(
        "realtime_session_channels",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=False),
        sa.Column("channel_type", sa.Text(), nullable=False, server_default=sa.text("'sse'")),
        sa.Column("channel_status", sa.Text(), nullable=False, server_default=sa.text("'created'")),
        sa.Column("transport_type", sa.Text(), nullable=False, server_default=sa.text("'sse'")),
        sa.Column("channel_label", sa.Text(), nullable=True),
        sa.Column("is_default_event_stream", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_send_events", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("can_receive_actions", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("permission_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("runtime_state_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        ck("channel_type", REALTIME_CHANNEL_TYPE_VALUES, "ck_rtsc_type"),
        ck("channel_status", REALTIME_CHANNEL_STATUS_VALUES, "ck_rtsc_status"),
        ck("transport_type", REALTIME_TRANSPORT_VALUES, "ck_rtsc_transport"),
    )
    op.create_index(
        "idx_rtsc_session_type",
        "realtime_session_channels",
        ["realtime_session_id", "channel_type", "channel_status"],
    )

    op.create_table(
        "realtime_session_state_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=False),
        sa.Column("actor_participant_id", postgresql.UUID, nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False, server_default=sa.text("'session.created'")),
        sa.Column("event_status", sa.Text(), nullable=False, server_default=sa.text("'recorded'")),
        sa.Column("previous_status", sa.Text(), nullable=True),
        sa.Column("next_status", sa.Text(), nullable=True),
        sa.Column("event_summary", sa.Text(), nullable=True),
        sa.Column("event_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("permission_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["actor_participant_id"], ["realtime_copresence_participants.id"]),
        ck("event_type", REALTIME_SESSION_EVENT_TYPE_VALUES, "ck_rtse_type"),
        ck("event_status", REALTIME_EVENT_STATUS_VALUES, "ck_rtse_status"),
    )
    op.create_index(
        "idx_rtse_session_occurred",
        "realtime_session_state_events",
        ["realtime_session_id", "occurred_at"],
    )

    op.create_table(
        "realtime_channel_state_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=False),
        sa.Column("channel_id", postgresql.UUID, nullable=False),
        sa.Column("actor_participant_id", postgresql.UUID, nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False, server_default=sa.text("'channel.created'")),
        sa.Column("event_status", sa.Text(), nullable=False, server_default=sa.text("'recorded'")),
        sa.Column("previous_status", sa.Text(), nullable=True),
        sa.Column("next_status", sa.Text(), nullable=True),
        sa.Column("event_summary", sa.Text(), nullable=True),
        sa.Column("event_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("permission_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["channel_id"], ["realtime_session_channels.id"]),
        sa.ForeignKeyConstraint(["actor_participant_id"], ["realtime_copresence_participants.id"]),
        ck("event_type", REALTIME_CHANNEL_EVENT_TYPE_VALUES, "ck_rtcse_type"),
        ck("event_status", REALTIME_EVENT_STATUS_VALUES, "ck_rtcse_status"),
    )
    op.create_index(
        "idx_rtcse_channel_occurred",
        "realtime_channel_state_events",
        ["channel_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_rtcse_channel_occurred", table_name="realtime_channel_state_events")
    op.drop_table("realtime_channel_state_events")

    op.drop_index("idx_rtse_session_occurred", table_name="realtime_session_state_events")
    op.drop_table("realtime_session_state_events")

    op.drop_index("idx_rtsc_session_type", table_name="realtime_session_channels")
    op.drop_table("realtime_session_channels")

    op.drop_index("idx_rtps_participant_current", table_name="realtime_participant_states")
    op.drop_table("realtime_participant_states")

    op.drop_index("idx_rtcp_co_presence_participant", table_name="realtime_copresence_participants")
    op.drop_index("idx_rtcp_session_role", table_name="realtime_copresence_participants")
    op.drop_table("realtime_copresence_participants")

    op.drop_index("idx_rtcs_active_companion_status", table_name="realtime_copresence_sessions")
    op.drop_index("idx_rtcs_co_presence_status", table_name="realtime_copresence_sessions")
    op.drop_index("idx_rtcs_user_status", table_name="realtime_copresence_sessions")
    op.drop_table("realtime_copresence_sessions")
