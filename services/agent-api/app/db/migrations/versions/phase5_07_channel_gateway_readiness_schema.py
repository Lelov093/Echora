"""phase5_07_channel_gateway_readiness_schema

Revision ID: p5_07_channel_gateway
Revises: p5_06_realtime_trace
Create Date: 2026-06-02 00:00:00.000000

Create Phase 5 Reoriented Companion Channel Gateway readiness schema. R7 is
schema-only: no Telegram, Discord, Feishu, WeChat, Slack, Matrix, Email, or
other real connector implementation; no platform SDK; no plaintext external
platform token storage; no frontend connector UI.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p5_07_channel_gateway"
down_revision: Union[str, Sequence[str], None] = "p5_06_realtime_trace"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BINDING_STATUS_VALUES = ("draft", "ready", "disabled", "revoked")
CHANNEL_KIND_VALUES = ("readiness_stub", "manual_placeholder", "future_external_channel")
CONNECTOR_KIND_VALUES = ("readiness_stub", "manual_placeholder")
IDENTITY_STATUS_VALUES = ("draft", "ready", "disabled", "revoked")
PERSONA_PROJECTION_POLICY_VALUES = ("disabled", "summary_only", "explicit_user_authorization")
CHANNEL_POLICY_STATUS_VALUES = ("draft", "active", "disabled", "revoked")
CHANNEL_ACCESS_POLICY_VALUES = ("disabled", "review_required", "explicit_user_authorization")
MESSAGE_DIRECTION_VALUES = ("inbound", "outbound", "system")
MESSAGE_STATUS_VALUES = ("queued", "recorded", "suppressed", "redacted")
MEMORY_CANDIDATE_POLICY_VALUES = ("deny", "review_required")
MEMORY_READ_SCOPE_VALUES = ("none", "low_risk_summary", "explicit_authorization")
MEMORY_WRITE_POLICY_VALUES = ("deny", "review_required")
AUDIT_EVENT_TYPE_VALUES = ("created", "permission_checked", "message_recorded", "boundary_applied", "revoked")
AUDIT_STATUS_VALUES = ("recorded", "review_required", "redacted")
REVOKE_STATUS_VALUES = ("requested", "applied", "failed")
REVOKE_SCOPE_VALUES = ("binding", "identity", "permission", "memory", "all")


def ck(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=name)


def jsonb_default() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.create_table(
        "presence_channel_bindings",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=True),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=True),
        sa.Column("binding_status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("channel_kind", sa.Text(), nullable=False, server_default=sa.text("'readiness_stub'")),
        sa.Column("connector_kind", sa.Text(), nullable=False, server_default=sa.text("'readiness_stub'")),
        sa.Column("external_channel_label", sa.Text(), nullable=True),
        sa.Column("external_channel_ref_hash", sa.Text(), nullable=True),
        sa.Column("stores_plaintext_token", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("credentials_ref", sa.Text(), nullable=True),
        sa.Column("can_receive_inbound", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_send_outbound", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_user_approval", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("readiness_notes", sa.Text(), nullable=True),
        sa.Column("permission_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("boundary_snapshot_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        ck("binding_status", BINDING_STATUS_VALUES, "ck_pcb_status"),
        ck("channel_kind", CHANNEL_KIND_VALUES, "ck_pcb_channel_kind"),
        ck("connector_kind", CONNECTOR_KIND_VALUES, "ck_pcb_connector_kind"),
        sa.CheckConstraint("stores_plaintext_token = false", name="ck_pcb_no_plaintext_token"),
        sa.CheckConstraint("can_send_outbound = false OR requires_user_approval = true", name="ck_pcb_outbound_requires_approval"),
    )
    op.create_index("idx_pcb_user_status", "presence_channel_bindings", ["user_id", "binding_status"])
    op.create_index("idx_pcb_companion_status", "presence_channel_bindings", ["companion_id", "binding_status"])
    op.create_index("idx_pcb_realtime_status", "presence_channel_bindings", ["realtime_session_id", "binding_status"])

    op.create_table(
        "companion_channel_identities",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("presence_channel_binding_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("identity_status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("external_identity_ref_hash", sa.Text(), nullable=True),
        sa.Column("persona_projection_policy", sa.Text(), nullable=False, server_default=sa.text("'summary_only'")),
        sa.Column("can_present_companion_identity", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("can_autonomously_message", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("identity_profile_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["presence_channel_binding_id"], ["presence_channel_bindings.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        ck("identity_status", IDENTITY_STATUS_VALUES, "ck_cci_status"),
        ck("persona_projection_policy", PERSONA_PROJECTION_POLICY_VALUES, "ck_cci_persona_projection"),
        sa.CheckConstraint("can_autonomously_message = false", name="ck_cci_no_autonomous_message"),
    )
    op.create_index("idx_cci_binding_status", "companion_channel_identities", ["presence_channel_binding_id", "identity_status"])
    op.create_index("idx_cci_companion_status", "companion_channel_identities", ["companion_id", "identity_status"])

    op.create_table(
        "channel_permission_policies",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("presence_channel_binding_id", postgresql.UUID, nullable=False),
        sa.Column("policy_status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("inbound_policy", sa.Text(), nullable=False, server_default=sa.text("'disabled'")),
        sa.Column("outbound_policy", sa.Text(), nullable=False, server_default=sa.text("'disabled'")),
        sa.Column("inbound_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("outbound_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_user_approval", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allows_memory_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allows_memory_write", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allows_raw_attachment_storage", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allows_unsolicited_message", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("permission_policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["presence_channel_binding_id"], ["presence_channel_bindings.id"]),
        ck("policy_status", CHANNEL_POLICY_STATUS_VALUES, "ck_cpp_status"),
        ck("inbound_policy", CHANNEL_ACCESS_POLICY_VALUES, "ck_cpp_inbound_policy"),
        ck("outbound_policy", CHANNEL_ACCESS_POLICY_VALUES, "ck_cpp_outbound_policy"),
        sa.CheckConstraint("requires_user_approval = true", name="ck_cpp_user_approval_required"),
        sa.CheckConstraint("outbound_enabled = false OR outbound_policy <> 'disabled'", name="ck_cpp_outbound_policy_enabled"),
        sa.CheckConstraint("inbound_enabled = false OR inbound_policy <> 'disabled'", name="ck_cpp_inbound_policy_enabled"),
        sa.CheckConstraint("allows_unsolicited_message = false", name="ck_cpp_no_unsolicited_message"),
        sa.CheckConstraint("allows_memory_write = false", name="ck_cpp_no_auto_memory_write"),
        sa.CheckConstraint("allows_raw_attachment_storage = false", name="ck_cpp_no_raw_attachment_storage"),
    )
    op.create_index("idx_cpp_binding_status", "channel_permission_policies", ["presence_channel_binding_id", "policy_status"])

    op.create_table(
        "channel_message_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("presence_channel_binding_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=True),
        sa.Column("realtime_session_id", postgresql.UUID, nullable=True),
        sa.Column("channel_permission_policy_id", postgresql.UUID, nullable=True),
        sa.Column("message_direction", sa.Text(), nullable=False),
        sa.Column("message_status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("message_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("raw_message_ref", sa.Text(), nullable=True),
        sa.Column("raw_message_storage_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("memory_candidate_policy", sa.Text(), nullable=False, server_default=sa.text("'review_required'")),
        sa.Column("requires_user_review", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("redaction_status", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("message_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["presence_channel_binding_id"], ["presence_channel_bindings.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["realtime_session_id"], ["realtime_copresence_sessions.id"]),
        sa.ForeignKeyConstraint(["channel_permission_policy_id"], ["channel_permission_policies.id"]),
        ck("message_direction", MESSAGE_DIRECTION_VALUES, "ck_cme_direction"),
        ck("message_status", MESSAGE_STATUS_VALUES, "ck_cme_status"),
        ck("memory_candidate_policy", MEMORY_CANDIDATE_POLICY_VALUES, "ck_cme_memory_policy"),
        ck("redaction_status", ("pending", "applied", "review_required", "failed"), "ck_cme_redaction"),
        sa.CheckConstraint("raw_message_ref IS NULL OR raw_message_storage_allowed = true", name="ck_cme_raw_ref_requires_storage"),
        sa.CheckConstraint("requires_user_review = true", name="ck_cme_review_required"),
        sa.CheckConstraint("memory_candidate_policy <> 'review_required' OR requires_user_review = true", name="ck_cme_memory_review_required"),
    )
    op.create_index("idx_cme_binding_direction", "channel_message_events", ["presence_channel_binding_id", "message_direction", "occurred_at"])
    op.create_index("idx_cme_realtime_status", "channel_message_events", ["realtime_session_id", "message_status"])
    op.create_index("idx_cme_companion_status", "channel_message_events", ["companion_id", "message_status"])

    op.create_table(
        "channel_memory_boundary_policies",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("presence_channel_binding_id", postgresql.UUID, nullable=False),
        sa.Column("policy_status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("memory_read_scope", sa.Text(), nullable=False, server_default=sa.text("'none'")),
        sa.Column("memory_write_policy", sa.Text(), nullable=False, server_default=sa.text("'deny'")),
        sa.Column("private_memory_access_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("shared_memory_write_requires_review", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("cross_companion_memory_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("raw_message_to_memory_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("boundary_policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["presence_channel_binding_id"], ["presence_channel_bindings.id"]),
        ck("policy_status", CHANNEL_POLICY_STATUS_VALUES, "ck_cmbp_status"),
        ck("memory_read_scope", MEMORY_READ_SCOPE_VALUES, "ck_cmbp_read_scope"),
        ck("memory_write_policy", MEMORY_WRITE_POLICY_VALUES, "ck_cmbp_write_policy"),
        sa.CheckConstraint("private_memory_access_allowed = false", name="ck_cmbp_no_private_memory_access"),
        sa.CheckConstraint("cross_companion_memory_allowed = false", name="ck_cmbp_no_cross_companion_memory"),
        sa.CheckConstraint("shared_memory_write_requires_review = true", name="ck_cmbp_shared_write_review"),
        sa.CheckConstraint("raw_message_to_memory_allowed = false", name="ck_cmbp_no_raw_to_memory"),
    )
    op.create_index("idx_cmbp_binding_status", "channel_memory_boundary_policies", ["presence_channel_binding_id", "policy_status"])

    op.create_table(
        "channel_audit_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("presence_channel_binding_id", postgresql.UUID, nullable=False),
        sa.Column("channel_message_event_id", postgresql.UUID, nullable=True),
        sa.Column("audit_event_type", sa.Text(), nullable=False, server_default=sa.text("'created'")),
        sa.Column("audit_status", sa.Text(), nullable=False, server_default=sa.text("'recorded'")),
        sa.Column("audit_summary", sa.Text(), nullable=True),
        sa.Column("audit_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["presence_channel_binding_id"], ["presence_channel_bindings.id"]),
        sa.ForeignKeyConstraint(["channel_message_event_id"], ["channel_message_events.id"]),
        ck("audit_event_type", AUDIT_EVENT_TYPE_VALUES, "ck_cae_type"),
        ck("audit_status", AUDIT_STATUS_VALUES, "ck_cae_status"),
    )
    op.create_index("idx_cae_binding_type", "channel_audit_events", ["presence_channel_binding_id", "audit_event_type", "occurred_at"])
    op.create_index("idx_cae_message_type", "channel_audit_events", ["channel_message_event_id", "audit_event_type"])

    op.create_table(
        "channel_revoke_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("presence_channel_binding_id", postgresql.UUID, nullable=False),
        sa.Column("revoke_status", sa.Text(), nullable=False, server_default=sa.text("'requested'")),
        sa.Column("revoke_scope", sa.Text(), nullable=False, server_default=sa.text("'all'")),
        sa.Column("revokes_credentials_ref", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("stops_inbound", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("stops_outbound", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("audit_required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("revoke_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["presence_channel_binding_id"], ["presence_channel_bindings.id"]),
        ck("revoke_status", REVOKE_STATUS_VALUES, "ck_cre_status"),
        ck("revoke_scope", REVOKE_SCOPE_VALUES, "ck_cre_scope"),
        sa.CheckConstraint("audit_required = true", name="ck_cre_audit_required"),
        sa.CheckConstraint("revokes_credentials_ref = true", name="ck_cre_revokes_credentials"),
        sa.CheckConstraint("stops_inbound = true OR stops_outbound = true", name="ck_cre_stops_channel"),
    )
    op.create_index("idx_cre_binding_status", "channel_revoke_events", ["presence_channel_binding_id", "revoke_status"])


def downgrade() -> None:
    op.drop_index("idx_cre_binding_status", table_name="channel_revoke_events")
    op.drop_table("channel_revoke_events")

    op.drop_index("idx_cae_message_type", table_name="channel_audit_events")
    op.drop_index("idx_cae_binding_type", table_name="channel_audit_events")
    op.drop_table("channel_audit_events")

    op.drop_index("idx_cmbp_binding_status", table_name="channel_memory_boundary_policies")
    op.drop_table("channel_memory_boundary_policies")

    op.drop_index("idx_cme_companion_status", table_name="channel_message_events")
    op.drop_index("idx_cme_realtime_status", table_name="channel_message_events")
    op.drop_index("idx_cme_binding_direction", table_name="channel_message_events")
    op.drop_table("channel_message_events")

    op.drop_index("idx_cpp_binding_status", table_name="channel_permission_policies")
    op.drop_table("channel_permission_policies")

    op.drop_index("idx_cci_companion_status", table_name="companion_channel_identities")
    op.drop_index("idx_cci_binding_status", table_name="companion_channel_identities")
    op.drop_table("companion_channel_identities")

    op.drop_index("idx_pcb_realtime_status", table_name="presence_channel_bindings")
    op.drop_index("idx_pcb_companion_status", table_name="presence_channel_bindings")
    op.drop_index("idx_pcb_user_status", table_name="presence_channel_bindings")
    op.drop_table("presence_channel_bindings")
