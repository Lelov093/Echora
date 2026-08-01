"""phase5_04_realtime_memory_buffer_schema

Revision ID: p5_04_realtime_memory
Revises: p5_03_multimodal_permission
Create Date: 2026-06-02 00:00:00.000000

Create Phase 5 Reoriented realtime memory buffer, salient moment, and
review-gated shared memory candidate schema. R4 is schema-only: no automatic
long-term memory write, no shared episodic memory write, no API, service, or
frontend implementation.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p5_04_realtime_memory"
down_revision: Union[str, Sequence[str], None] = "p5_03_multimodal_permission"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BUFFER_SCOPE_VALUES = ("companion_private", "co_presence_session", "shared_scene")
BUFFER_STATUS_VALUES = ("active", "paused", "expired", "archived")
MEMORY_ACTION_VALUES = ("none", "candidate_review", "explicit_user_authorization")
RETENTION_POLICY_VALUES = ("ephemeral", "review_summary_only", "explicit_retention")

BUFFER_ITEM_SOURCE_VALUES = (
    "voice_turn",
    "transcript",
    "multimodal_context",
    "session_event",
    "channel_event",
    "manual_note",
)
BUFFER_ITEM_STATUS_VALUES = ("active", "expired", "redacted", "archived")

SALIENT_SCOPE_VALUES = ("companion_private", "shared_scene", "shared_episodic")
SALIENT_STATUS_VALUES = ("candidate_pending_review", "approved", "rejected", "archived")
REALTIME_CANDIDATE_STATUS_VALUES = ("pending_review", "approved", "rejected", "committed", "archived")
SYNC_POLICY_VALUES = ("review_required", "explicit_user_authorization", "deny")
EXPIRY_STATUS_VALUES = ("scheduled", "completed", "cancelled", "failed")


def ck(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=name)


def jsonb_default() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "realtime_memory_buffers",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=True),
        sa.Column("shared_scene_id", postgresql.UUID, nullable=True),
        sa.Column("owner_companion_id", postgresql.UUID, nullable=True),
        sa.Column("buffer_scope", sa.Text(), nullable=False, server_default=sa.text("'co_presence_session'")),
        sa.Column("buffer_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("default_memory_action", sa.Text(), nullable=False, server_default=sa.text("'candidate_review'")),
        sa.Column("retention_policy", sa.Text(), nullable=False, server_default=sa.text("'ephemeral'")),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_write_private_memory", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("auto_write_shared_memory", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("buffer_summary", sa.Text(), nullable=True),
        sa.Column("policy_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["shared_scene_id"], ["shared_scenes.id"]),
        sa.ForeignKeyConstraint(["owner_companion_id"], ["companions.id"]),
        ck("buffer_scope", BUFFER_SCOPE_VALUES, "ck_rmb_scope"),
        ck("buffer_status", BUFFER_STATUS_VALUES, "ck_rmb_status"),
        ck("default_memory_action", MEMORY_ACTION_VALUES, "ck_rmb_action"),
        ck("retention_policy", RETENTION_POLICY_VALUES, "ck_rmb_retention"),
        sa.CheckConstraint("auto_write_private_memory = false", name="ck_rmb_no_auto_private"),
        sa.CheckConstraint("auto_write_shared_memory = false", name="ck_rmb_no_auto_shared"),
        sa.CheckConstraint(
            "(buffer_scope <> 'companion_private' OR owner_companion_id IS NOT NULL)",
            name="ck_rmb_private_owner",
        ),
        sa.CheckConstraint(
            "(buffer_scope <> 'shared_scene' OR shared_scene_id IS NOT NULL)",
            name="ck_rmb_shared_scene",
        ),
    )
    op.create_index("idx_rmb_realtime_scope", "realtime_memory_buffers", ["realtime_session_id", "buffer_scope", "buffer_status"])
    op.create_index("idx_rmb_expires", "realtime_memory_buffers", ["expires_at", "buffer_status"])

    op.create_table(
        "realtime_memory_buffer_items",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("buffer_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False, server_default=sa.text("'session_event'")),
        sa.Column("source_voice_turn_id", postgresql.UUID, nullable=True),
        sa.Column("source_context_event_id", postgresql.UUID, nullable=True),
        sa.Column("source_session_event_id", postgresql.UUID, nullable=True),
        sa.Column("source_channel_event_id", postgresql.UUID, nullable=True),
        sa.Column("item_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("retention_policy", sa.Text(), nullable=False, server_default=sa.text("'ephemeral'")),
        sa.Column("content_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("raw_content_ref", sa.Text(), nullable=True),
        sa.Column("can_generate_salient_moment", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("can_write_long_term_memory", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["buffer_id"], ["realtime_memory_buffers.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["source_voice_turn_id"], ["voice_turns.id"]),
        sa.ForeignKeyConstraint(["source_context_event_id"], ["multimodal_context_events.id"]),
        sa.ForeignKeyConstraint(["source_session_event_id"], ["realtime_session_state_events.id"]),
        sa.ForeignKeyConstraint(["source_channel_event_id"], ["realtime_channel_state_events.id"]),
        ck("source_type", BUFFER_ITEM_SOURCE_VALUES, "ck_rmbi_source"),
        ck("item_status", BUFFER_ITEM_STATUS_VALUES, "ck_rmbi_status"),
        ck("retention_policy", RETENTION_POLICY_VALUES, "ck_rmbi_retention"),
        sa.CheckConstraint("can_write_long_term_memory = false", name="ck_rmbi_no_direct_write"),
    )
    op.create_index("idx_rmbi_buffer_created", "realtime_memory_buffer_items", ["buffer_id", "created_at"])

    op.create_table(
        "companion_private_realtime_buffers",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("buffer_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("private_memory_sync_policy", sa.Text(), nullable=False, server_default=sa.text("'review_required'")),
        sa.Column("auto_write_private_memory", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["buffer_id"], ["realtime_memory_buffers.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.UniqueConstraint("buffer_id", name="uq_cprb_buffer"),
        ck("private_memory_sync_policy", SYNC_POLICY_VALUES, "ck_cprb_sync"),
        sa.CheckConstraint("auto_write_private_memory = false", name="ck_cprb_no_auto_write"),
    )
    op.create_index("idx_cprb_companion", "companion_private_realtime_buffers", ["companion_id", "review_required"])

    op.create_table(
        "copresence_session_buffers",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("buffer_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=False),
        sa.Column("shared_candidate_policy", sa.Text(), nullable=False, server_default=sa.text("'review_required'")),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["buffer_id"], ["realtime_memory_buffers.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.UniqueConstraint("buffer_id", name="uq_csb_buffer"),
        ck("shared_candidate_policy", SYNC_POLICY_VALUES, "ck_csb_sync"),
    )
    op.create_index("idx_csb_session", "copresence_session_buffers", ["co_presence_session_id", "review_required"])

    op.create_table(
        "shared_scene_buffers",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("buffer_id", postgresql.UUID, nullable=False),
        sa.Column("shared_scene_id", postgresql.UUID, nullable=False),
        sa.Column("shared_candidate_policy", sa.Text(), nullable=False, server_default=sa.text("'review_required'")),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["buffer_id"], ["realtime_memory_buffers.id"]),
        sa.ForeignKeyConstraint(["shared_scene_id"], ["shared_scenes.id"]),
        sa.UniqueConstraint("buffer_id", name="uq_ssb_buffer"),
        ck("shared_candidate_policy", SYNC_POLICY_VALUES, "ck_ssb_sync"),
    )
    op.create_index("idx_ssb_scene", "shared_scene_buffers", ["shared_scene_id", "review_required"])

    op.create_table(
        "salient_moments",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=False),
        sa.Column("buffer_id", postgresql.UUID, nullable=False),
        sa.Column("buffer_item_id", postgresql.UUID, nullable=True),
        sa.Column("moment_scope", sa.Text(), nullable=False, server_default=sa.text("'shared_episodic'")),
        sa.Column("moment_status", sa.Text(), nullable=False, server_default=sa.text("'candidate_pending_review'")),
        sa.Column("moment_title", sa.Text(), nullable=True),
        sa.Column("moment_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("salience_score", sa.Double(), nullable=False, server_default=sa.text("0.5")),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_write_disabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("policy_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["buffer_id"], ["realtime_memory_buffers.id"]),
        sa.ForeignKeyConstraint(["buffer_item_id"], ["realtime_memory_buffer_items.id"]),
        ck("moment_scope", SALIENT_SCOPE_VALUES, "ck_sm_scope"),
        ck("moment_status", SALIENT_STATUS_VALUES, "ck_sm_status"),
        sa.CheckConstraint("review_required = true", name="ck_sm_review_required"),
        sa.CheckConstraint("auto_write_disabled = true", name="ck_sm_no_auto_write"),
        sa.CheckConstraint("salience_score BETWEEN 0 AND 1", name="ck_sm_salience"),
    )
    op.create_index("idx_sm_realtime_status", "salient_moments", ["realtime_session_id", "moment_status", "created_at"])

    op.create_table(
        "companion_private_salient_moments",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("salient_moment_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("private_memory_sync_policy", sa.Text(), nullable=False, server_default=sa.text("'review_required'")),
        sa.Column("approved_private_memory_id", postgresql.UUID, nullable=True),
        sa.Column("auto_write_private_memory", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["salient_moment_id"], ["salient_moments.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["approved_private_memory_id"], ["memories.id"]),
        sa.UniqueConstraint("salient_moment_id", "companion_id", name="uq_cpsm_moment_companion"),
        ck("private_memory_sync_policy", SYNC_POLICY_VALUES, "ck_cpsm_sync"),
        sa.CheckConstraint("auto_write_private_memory = false", name="ck_cpsm_no_auto_write"),
    )
    op.create_index("idx_cpsm_companion", "companion_private_salient_moments", ["companion_id", "review_required"])

    op.create_table(
        "shared_salient_moments",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("salient_moment_id", postgresql.UUID, nullable=False),
        sa.Column("shared_scene_id", postgresql.UUID, nullable=True),
        sa.Column("proposed_shared_memory_candidate_id", postgresql.UUID, nullable=True),
        sa.Column("shared_memory_sync_policy", sa.Text(), nullable=False, server_default=sa.text("'review_required'")),
        sa.Column("auto_write_shared_memory", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["salient_moment_id"], ["salient_moments.id"]),
        sa.ForeignKeyConstraint(["shared_scene_id"], ["shared_scenes.id"]),
        sa.ForeignKeyConstraint(["proposed_shared_memory_candidate_id"], ["shared_memory_candidates.id"]),
        sa.UniqueConstraint("salient_moment_id", name="uq_ssm_moment"),
        ck("shared_memory_sync_policy", SYNC_POLICY_VALUES, "ck_ssm_sync"),
        sa.CheckConstraint("auto_write_shared_memory = false", name="ck_ssm_no_auto_write"),
    )
    op.create_index("idx_ssm_scene", "shared_salient_moments", ["shared_scene_id", "review_required"])

    op.create_table(
        "realtime_shared_memory_candidates",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=False),
        sa.Column("salient_moment_id", postgresql.UUID, nullable=False),
        sa.Column("source_buffer_id", postgresql.UUID, nullable=False),
        sa.Column("source_buffer_item_id", postgresql.UUID, nullable=True),
        sa.Column("proposed_shared_memory_candidate_id", postgresql.UUID, nullable=True),
        sa.Column("candidate_status", sa.Text(), nullable=False, server_default=sa.text("'pending_review'")),
        sa.Column("candidate_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("requires_user_review", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_commit_shared_memory", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("shared_to_private_policy", sa.Text(), nullable=False, server_default=sa.text("'review_required'")),
        sa.Column("private_to_shared_policy", sa.Text(), nullable=False, server_default=sa.text("'review_required'")),
        sa.Column("candidate_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["salient_moment_id"], ["salient_moments.id"]),
        sa.ForeignKeyConstraint(["source_buffer_id"], ["realtime_memory_buffers.id"]),
        sa.ForeignKeyConstraint(["source_buffer_item_id"], ["realtime_memory_buffer_items.id"]),
        sa.ForeignKeyConstraint(["proposed_shared_memory_candidate_id"], ["shared_memory_candidates.id"]),
        ck("candidate_status", REALTIME_CANDIDATE_STATUS_VALUES, "ck_rsmc_status"),
        ck("shared_to_private_policy", SYNC_POLICY_VALUES, "ck_rsmc_shared_to_private"),
        ck("private_to_shared_policy", SYNC_POLICY_VALUES, "ck_rsmc_private_to_shared"),
        sa.CheckConstraint("requires_user_review = true", name="ck_rsmc_review_required"),
        sa.CheckConstraint("auto_commit_shared_memory = false", name="ck_rsmc_no_auto_commit"),
    )
    op.create_index("idx_rsmc_realtime_status", "realtime_shared_memory_candidates", ["realtime_session_id", "candidate_status", "created_at"])

    op.create_table(
        "realtime_memory_expiry_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("buffer_id", postgresql.UUID, nullable=True),
        sa.Column("buffer_item_id", postgresql.UUID, nullable=True),
        sa.Column("salient_moment_id", postgresql.UUID, nullable=True),
        sa.Column("expiry_status", sa.Text(), nullable=False, server_default=sa.text("'scheduled'")),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_data_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("expiry_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["buffer_id"], ["realtime_memory_buffers.id"]),
        sa.ForeignKeyConstraint(["buffer_item_id"], ["realtime_memory_buffer_items.id"]),
        sa.ForeignKeyConstraint(["salient_moment_id"], ["salient_moments.id"]),
        ck("expiry_status", EXPIRY_STATUS_VALUES, "ck_rmee_status"),
        sa.CheckConstraint(
            "(buffer_id IS NOT NULL OR buffer_item_id IS NOT NULL OR salient_moment_id IS NOT NULL)",
            name="ck_rmee_target",
        ),
    )
    op.create_index("idx_rmee_buffer_status", "realtime_memory_expiry_events", ["buffer_id", "expiry_status"])
    op.create_index("idx_rmee_scheduled", "realtime_memory_expiry_events", ["scheduled_for", "expiry_status"])


def downgrade() -> None:
    op.drop_index("idx_rmee_scheduled", table_name="realtime_memory_expiry_events")
    op.drop_index("idx_rmee_buffer_status", table_name="realtime_memory_expiry_events")
    op.drop_table("realtime_memory_expiry_events")

    op.drop_index("idx_rsmc_realtime_status", table_name="realtime_shared_memory_candidates")
    op.drop_table("realtime_shared_memory_candidates")

    op.drop_index("idx_ssm_scene", table_name="shared_salient_moments")
    op.drop_table("shared_salient_moments")

    op.drop_index("idx_cpsm_companion", table_name="companion_private_salient_moments")
    op.drop_table("companion_private_salient_moments")

    op.drop_index("idx_sm_realtime_status", table_name="salient_moments")
    op.drop_table("salient_moments")

    op.drop_index("idx_ssb_scene", table_name="shared_scene_buffers")
    op.drop_table("shared_scene_buffers")

    op.drop_index("idx_csb_session", table_name="copresence_session_buffers")
    op.drop_table("copresence_session_buffers")

    op.drop_index("idx_cprb_companion", table_name="companion_private_realtime_buffers")
    op.drop_table("companion_private_realtime_buffers")

    op.drop_index("idx_rmbi_buffer_created", table_name="realtime_memory_buffer_items")
    op.drop_table("realtime_memory_buffer_items")

    op.drop_index("idx_rmb_expires", table_name="realtime_memory_buffers")
    op.drop_index("idx_rmb_realtime_scope", table_name="realtime_memory_buffers")
    op.drop_table("realtime_memory_buffers")
