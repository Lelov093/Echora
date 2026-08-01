"""phase5_03_multimodal_permission_schema

Revision ID: p5_03_multimodal_permission
Revises: p5_02_companion_voice
Create Date: 2026-06-02 00:00:00.000000

Create Phase 5 Reoriented multimodal context, participant visibility,
permission, retention, redaction, and expiry schema. R3 is schema-only:
no background screen capture, camera capture, system listener, connector,
API, service, or frontend implementation.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p5_03_multimodal_permission"
down_revision: Union[str, Sequence[str], None] = "p5_02_companion_voice"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


CONTEXT_TYPE_VALUES = ("image", "screen", "file", "device")
CONTEXT_SOURCE_VALUES = ("user_upload", "user_paste", "manual_summary", "session_event", "test")
CONTEXT_STATUS_VALUES = ("created", "active", "expired", "redacted", "blocked", "archived")
RETENTION_POLICY_VALUES = ("ephemeral", "review_summary_only", "explicit_retention")
REDACTION_STATUS_VALUES = ("not_required", "pending", "redacted", "failed")
CONTEXT_PERMISSION_SOURCE_VALUES = ("session_default", "user_grant", "user_override", "policy", "review_decision")
CONTEXT_EXPIRY_STATUS_VALUES = ("scheduled", "completed", "cancelled", "failed")

DEVICE_EVENT_KIND_VALUES = ("clipboard", "active_window", "notification", "system_status", "manual_device_note")
SCREEN_CONTEXT_KIND_VALUES = ("manual_summary", "screenshot_reference", "window_summary", "page_summary")
IMAGE_CONTEXT_KIND_VALUES = ("image_reference", "image_summary", "multi_image_summary")
FILE_CONTEXT_KIND_VALUES = ("file_reference", "file_excerpt", "file_summary")


def ck(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=name)


def jsonb_default() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "multimodal_context_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID, nullable=True),
        sa.Column("shared_scene_id", postgresql.UUID, nullable=True),
        sa.Column("source_participant_id", postgresql.UUID, nullable=True),
        sa.Column("context_type", sa.Text(), nullable=False),
        sa.Column("context_source", sa.Text(), nullable=False, server_default=sa.text("'session_event'")),
        sa.Column("context_status", sa.Text(), nullable=False, server_default=sa.text("'created'")),
        sa.Column("title", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("raw_data_ref", sa.Text(), nullable=True),
        sa.Column("raw_data_digest", sa.Text(), nullable=True),
        sa.Column("raw_data_retention_policy", sa.Text(), nullable=False, server_default=sa.text("'ephemeral'")),
        sa.Column("raw_data_storage_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("retention_policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("permission_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("visibility_summary_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("redaction_status", sa.Text(), nullable=False, server_default=sa.text("'not_required'")),
        sa.Column("redaction_summary", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["shared_scene_id"], ["shared_scenes.id"]),
        sa.ForeignKeyConstraint(["source_participant_id"], ["realtime_copresence_participants.id"]),
        ck("context_type", CONTEXT_TYPE_VALUES, "ck_mce_type"),
        ck("context_source", CONTEXT_SOURCE_VALUES, "ck_mce_source"),
        ck("context_status", CONTEXT_STATUS_VALUES, "ck_mce_status"),
        ck("raw_data_retention_policy", RETENTION_POLICY_VALUES, "ck_mce_retention"),
        ck("redaction_status", REDACTION_STATUS_VALUES, "ck_mce_redaction"),
        sa.CheckConstraint(
            "(raw_data_retention_policy <> 'ephemeral' OR raw_data_storage_allowed = false)",
            name="ck_mce_ephemeral_no_raw_storage",
        ),
        sa.CheckConstraint(
            "(raw_data_retention_policy <> 'explicit_retention' OR raw_data_storage_allowed = true)",
            name="ck_mce_explicit_retention_storage",
        ),
    )
    op.create_index(
        "idx_mce_realtime_type_status",
        "multimodal_context_events",
        ["realtime_session_id", "context_type", "context_status", "occurred_at"],
    )
    op.create_index("idx_mce_expires", "multimodal_context_events", ["expires_at", "context_status"])

    op.create_table(
        "image_context_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("context_event_id", postgresql.UUID, nullable=False),
        sa.Column("image_context_kind", sa.Text(), nullable=False, server_default=sa.text("'image_reference'")),
        sa.Column("image_count", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("image_ref_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("image_summary", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["context_event_id"], ["multimodal_context_events.id"]),
        sa.UniqueConstraint("context_event_id", name="uq_ice_context_event"),
        ck("image_context_kind", IMAGE_CONTEXT_KIND_VALUES, "ck_ice_kind"),
        sa.CheckConstraint("image_count BETWEEN 1 AND 64", name="ck_ice_count"),
    )
    op.create_index("idx_ice_context", "image_context_events", ["context_event_id"])

    op.create_table(
        "screen_context_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("context_event_id", postgresql.UUID, nullable=False),
        sa.Column("screen_context_kind", sa.Text(), nullable=False, server_default=sa.text("'manual_summary'")),
        sa.Column("window_title", sa.Text(), nullable=True),
        sa.Column("screen_summary", sa.Text(), nullable=True),
        sa.Column("capture_ref", sa.Text(), nullable=True),
        sa.Column("requires_manual_user_action", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["context_event_id"], ["multimodal_context_events.id"]),
        sa.UniqueConstraint("context_event_id", name="uq_sce_context_event"),
        ck("screen_context_kind", SCREEN_CONTEXT_KIND_VALUES, "ck_sce_kind"),
        sa.CheckConstraint("requires_manual_user_action = true", name="ck_sce_manual_only"),
    )
    op.create_index("idx_sce_context", "screen_context_events", ["context_event_id"])

    op.create_table(
        "file_context_realtime_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("context_event_id", postgresql.UUID, nullable=False),
        sa.Column("file_context_kind", sa.Text(), nullable=False, server_default=sa.text("'file_reference'")),
        sa.Column("file_document_id", postgresql.UUID, nullable=True),
        sa.Column("file_name", sa.Text(), nullable=True),
        sa.Column("file_mime_type", sa.Text(), nullable=True),
        sa.Column("file_ref", sa.Text(), nullable=True),
        sa.Column("excerpt_text", sa.Text(), nullable=True),
        sa.Column("file_summary", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["context_event_id"], ["multimodal_context_events.id"]),
        sa.ForeignKeyConstraint(["file_document_id"], ["file_documents.id"]),
        sa.UniqueConstraint("context_event_id", name="uq_fcre_context_event"),
        ck("file_context_kind", FILE_CONTEXT_KIND_VALUES, "ck_fcre_kind"),
    )
    op.create_index("idx_fcre_context", "file_context_realtime_events", ["context_event_id"])
    op.create_index("idx_fcre_file_document", "file_context_realtime_events", ["file_document_id"])

    op.create_table(
        "device_context_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("context_event_id", postgresql.UUID, nullable=False),
        sa.Column("device_event_kind", sa.Text(), nullable=False, server_default=sa.text("'manual_device_note'")),
        sa.Column("device_label", sa.Text(), nullable=True),
        sa.Column("event_summary", sa.Text(), nullable=True),
        sa.Column("requires_manual_user_action", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("device_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["context_event_id"], ["multimodal_context_events.id"]),
        sa.UniqueConstraint("context_event_id", name="uq_dce_context_event"),
        ck("device_event_kind", DEVICE_EVENT_KIND_VALUES, "ck_dce_kind"),
        sa.CheckConstraint("requires_manual_user_action = true", name="ck_dce_manual_only"),
    )
    op.create_index("idx_dce_context", "device_context_events", ["context_event_id"])

    op.create_table(
        "participant_context_permissions",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("context_event_id", postgresql.UUID, nullable=False),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=False),
        sa.Column("participant_id", postgresql.UUID, nullable=False),
        sa.Column("permission_source", sa.Text(), nullable=False, server_default=sa.text("'session_default'")),
        sa.Column("can_see", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_use", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_remember", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_view_raw_data", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("review_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("permission_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("boundary_policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["context_event_id"], ["multimodal_context_events.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["participant_id"], ["realtime_copresence_participants.id"]),
        sa.UniqueConstraint("context_event_id", "participant_id", name="uq_pcp_context_participant"),
        ck("permission_source", CONTEXT_PERMISSION_SOURCE_VALUES, "ck_pcp_source"),
        sa.CheckConstraint(
            "(can_remember = false OR review_required = true)",
            name="ck_pcp_remember_requires_review",
        ),
        sa.CheckConstraint(
            "(can_view_raw_data = false OR can_see = true)",
            name="ck_pcp_raw_requires_see",
        ),
    )
    op.create_index("idx_pcp_context_participant", "participant_context_permissions", ["context_event_id", "participant_id"])
    op.create_index("idx_pcp_participant", "participant_context_permissions", ["participant_id", "can_see", "can_remember"])

    op.create_table(
        "context_retention_policies",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("context_event_id", postgresql.UUID, nullable=True),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=True),
        sa.Column("policy_scope", sa.Text(), nullable=False, server_default=sa.text("'context_event'")),
        sa.Column("retention_policy", sa.Text(), nullable=False, server_default=sa.text("'ephemeral'")),
        sa.Column("redaction_status", sa.Text(), nullable=False, server_default=sa.text("'not_required'")),
        sa.Column("raw_data_storage_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["context_event_id"], ["multimodal_context_events.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.CheckConstraint("policy_scope IN ('context_event', 'realtime_session')", name="ck_crp_scope"),
        ck("retention_policy", RETENTION_POLICY_VALUES, "ck_crp_retention"),
        ck("redaction_status", REDACTION_STATUS_VALUES, "ck_crp_redaction"),
        sa.CheckConstraint(
            "(context_event_id IS NOT NULL OR realtime_session_id IS NOT NULL)",
            name="ck_crp_target",
        ),
        sa.CheckConstraint(
            "(retention_policy <> 'ephemeral' OR raw_data_storage_allowed = false)",
            name="ck_crp_ephemeral_no_raw_storage",
        ),
    )
    op.create_index("idx_crp_context", "context_retention_policies", ["context_event_id", "retention_policy"])
    op.create_index("idx_crp_expires", "context_retention_policies", ["expires_at", "retention_policy"])

    op.create_table(
        "ephemeral_context_expiry_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("context_event_id", postgresql.UUID, nullable=False),
        sa.Column("retention_policy_id", postgresql.UUID, nullable=True),
        sa.Column("expiry_status", sa.Text(), nullable=False, server_default=sa.text("'scheduled'")),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_data_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("redaction_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("expiry_summary", sa.Text(), nullable=True),
        sa.Column("expiry_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["context_event_id"], ["multimodal_context_events.id"]),
        sa.ForeignKeyConstraint(["retention_policy_id"], ["context_retention_policies.id"]),
        ck("expiry_status", CONTEXT_EXPIRY_STATUS_VALUES, "ck_ecee_status"),
    )
    op.create_index("idx_ecee_context_status", "ephemeral_context_expiry_events", ["context_event_id", "expiry_status"])
    op.create_index("idx_ecee_scheduled", "ephemeral_context_expiry_events", ["scheduled_for", "expiry_status"])


def downgrade() -> None:
    op.drop_index("idx_ecee_scheduled", table_name="ephemeral_context_expiry_events")
    op.drop_index("idx_ecee_context_status", table_name="ephemeral_context_expiry_events")
    op.drop_table("ephemeral_context_expiry_events")

    op.drop_index("idx_crp_expires", table_name="context_retention_policies")
    op.drop_index("idx_crp_context", table_name="context_retention_policies")
    op.drop_table("context_retention_policies")

    op.drop_index("idx_pcp_participant", table_name="participant_context_permissions")
    op.drop_index("idx_pcp_context_participant", table_name="participant_context_permissions")
    op.drop_table("participant_context_permissions")

    op.drop_index("idx_dce_context", table_name="device_context_events")
    op.drop_table("device_context_events")

    op.drop_index("idx_fcre_file_document", table_name="file_context_realtime_events")
    op.drop_index("idx_fcre_context", table_name="file_context_realtime_events")
    op.drop_table("file_context_realtime_events")

    op.drop_index("idx_sce_context", table_name="screen_context_events")
    op.drop_table("screen_context_events")

    op.drop_index("idx_ice_context", table_name="image_context_events")
    op.drop_table("image_context_events")

    op.drop_index("idx_mce_expires", table_name="multimodal_context_events")
    op.drop_index("idx_mce_realtime_type_status", table_name="multimodal_context_events")
    op.drop_table("multimodal_context_events")
