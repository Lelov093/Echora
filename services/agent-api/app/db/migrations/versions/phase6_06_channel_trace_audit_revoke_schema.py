"""phase6_06_channel_trace_audit_revoke_schema

Revision ID: p6_06_channel_trace
Revises: p6_05_channel_presence
Create Date: 2026-06-03 00:00:00.000000

Create Phase 6 Channel Trace / Audit / Revoke schema. All external channel
behavior must be auditable, revocable, and connected to boundary, permission,
memory gate, and delivery evidence.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p6_06_channel_trace"
down_revision: Union[str, Sequence[str], None] = "p6_05_channel_presence"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TRACE_EVENT_TYPE_VALUES = ("binding", "inbound", "outbound", "memory_gate", "presence_policy", "revoke", "adapter")
TRACE_STATUS_VALUES = ("recorded", "suppressed", "redacted", "failed")
AUDIT_LOG_TYPE_VALUES = ("binding_created", "binding_updated", "message_received", "message_sent", "memory_candidate_created", "checkin_suppressed", "revoked")
BINDING_STATUS_EVENT_VALUES = ("created", "activated", "disabled", "revoked", "restored")
OUTBOUND_AUDIT_STATUS_VALUES = ("queued", "sent", "suppressed", "failed", "rate_limited")
MEMORY_GATE_DECISION_VALUES = ("candidate_created", "ignored_low_salience", "blocked_by_policy", "redacted", "review_required")
MEMORY_GATE_STATUS_VALUES = ("recorded", "review_required", "redacted")


def ck(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=name)


def jsonb_default() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.add_column("channel_revoke_events", sa.Column("channel_binding_id", postgresql.UUID, nullable=True))
    op.add_column("channel_revoke_events", sa.Column("provider_id", postgresql.UUID, nullable=True))
    op.add_column("channel_revoke_events", sa.Column("provider_bot_id", postgresql.UUID, nullable=True))
    op.add_column("channel_revoke_events", sa.Column("trace_run_id", postgresql.UUID, nullable=True))
    op.add_column(
        "channel_revoke_events",
        sa.Column("stops_checkins", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "channel_revoke_events",
        sa.Column("clears_ephemeral_buffer", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "channel_revoke_events",
        sa.Column("disables_memory_candidates", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_foreign_key("fk_cre_phase6_channel_binding", "channel_revoke_events", "channel_bindings", ["channel_binding_id"], ["id"])
    op.create_foreign_key("fk_cre_phase6_provider", "channel_revoke_events", "channel_providers", ["provider_id"], ["id"])
    op.create_foreign_key("fk_cre_phase6_provider_bot", "channel_revoke_events", "channel_bot_registries", ["provider_bot_id"], ["id"])
    op.create_foreign_key("fk_cre_phase6_trace_run", "channel_revoke_events", "trace_runs", ["trace_run_id"], ["id"])
    op.create_check_constraint("ck_cre_phase6_stops_checkins", "channel_revoke_events", "stops_checkins = true")
    op.create_check_constraint("ck_cre_phase6_clears_buffer", "channel_revoke_events", "clears_ephemeral_buffer = true")
    op.create_check_constraint("ck_cre_phase6_disables_candidates", "channel_revoke_events", "disables_memory_candidates = true")
    op.create_index("idx_cre_phase6_channel_binding", "channel_revoke_events", ["channel_binding_id", "revoke_status"])
    op.create_index("idx_cre_phase6_trace_run", "channel_revoke_events", ["trace_run_id"])

    op.create_table(
        "channel_trace_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=True),
        sa.Column("channel_binding_id", postgresql.UUID, nullable=True),
        sa.Column("provider_id", postgresql.UUID, nullable=True),
        sa.Column("provider_bot_id", postgresql.UUID, nullable=True),
        sa.Column("trace_run_id", postgresql.UUID, nullable=True),
        sa.Column("channel_message_event_id", postgresql.UUID, nullable=True),
        sa.Column("channel_delivery_event_id", postgresql.UUID, nullable=True),
        sa.Column("trace_event_type", sa.Text(), nullable=False),
        sa.Column("trace_status", sa.Text(), nullable=False, server_default=sa.text("'recorded'")),
        sa.Column("trace_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("safe_trace_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["channel_binding_id"], ["channel_bindings.id"]),
        sa.ForeignKeyConstraint(["provider_id"], ["channel_providers.id"]),
        sa.ForeignKeyConstraint(["provider_bot_id"], ["channel_bot_registries.id"]),
        sa.ForeignKeyConstraint(["trace_run_id"], ["trace_runs.id"]),
        sa.ForeignKeyConstraint(["channel_message_event_id"], ["channel_message_events.id"]),
        sa.ForeignKeyConstraint(["channel_delivery_event_id"], ["channel_delivery_events.id"]),
        ck("trace_event_type", TRACE_EVENT_TYPE_VALUES, "ck_channel_trace_events_type"),
        ck("trace_status", TRACE_STATUS_VALUES, "ck_channel_trace_events_status"),
    )
    op.create_index("idx_channel_trace_events_binding_type", "channel_trace_events", ["channel_binding_id", "trace_event_type", "occurred_at"])
    op.create_index("idx_channel_trace_events_trace_run", "channel_trace_events", ["trace_run_id"])

    op.create_table(
        "channel_audit_logs",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("channel_binding_id", postgresql.UUID, nullable=True),
        sa.Column("provider_id", postgresql.UUID, nullable=True),
        sa.Column("provider_bot_id", postgresql.UUID, nullable=True),
        sa.Column("channel_trace_event_id", postgresql.UUID, nullable=True),
        sa.Column("audit_log_type", sa.Text(), nullable=False),
        sa.Column("audit_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("safe_audit_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["channel_binding_id"], ["channel_bindings.id"]),
        sa.ForeignKeyConstraint(["provider_id"], ["channel_providers.id"]),
        sa.ForeignKeyConstraint(["provider_bot_id"], ["channel_bot_registries.id"]),
        sa.ForeignKeyConstraint(["channel_trace_event_id"], ["channel_trace_events.id"]),
        ck("audit_log_type", AUDIT_LOG_TYPE_VALUES, "ck_channel_audit_logs_type"),
    )
    op.create_index("idx_channel_audit_logs_binding_time", "channel_audit_logs", ["channel_binding_id", "occurred_at"])
    op.create_index("idx_channel_audit_logs_trace", "channel_audit_logs", ["channel_trace_event_id"])

    op.create_table(
        "channel_binding_status_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("channel_binding_id", postgresql.UUID, nullable=False),
        sa.Column("status_event", sa.Text(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("status_reason", sa.Text(), nullable=True),
        sa.Column("safe_status_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["channel_binding_id"], ["channel_bindings.id"]),
        ck("status_event", BINDING_STATUS_EVENT_VALUES, "ck_channel_binding_status_events_event"),
    )
    op.create_index("idx_channel_binding_status_events_binding_time", "channel_binding_status_events", ["channel_binding_id", "occurred_at"])

    op.create_table(
        "channel_outbound_audit_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("channel_binding_id", postgresql.UUID, nullable=False),
        sa.Column("channel_delivery_event_id", postgresql.UUID, nullable=True),
        sa.Column("channel_message_event_id", postgresql.UUID, nullable=True),
        sa.Column("provider_bot_id", postgresql.UUID, nullable=True),
        sa.Column("outbound_audit_status", sa.Text(), nullable=False),
        sa.Column("outbound_policy_snapshot", sa.Text(), nullable=False, server_default=sa.text("'reply_only'")),
        sa.Column("audit_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("safe_outbound_audit_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["channel_binding_id"], ["channel_bindings.id"]),
        sa.ForeignKeyConstraint(["channel_delivery_event_id"], ["channel_delivery_events.id"]),
        sa.ForeignKeyConstraint(["channel_message_event_id"], ["channel_message_events.id"]),
        sa.ForeignKeyConstraint(["provider_bot_id"], ["channel_bot_registries.id"]),
        ck("outbound_audit_status", OUTBOUND_AUDIT_STATUS_VALUES, "ck_channel_outbound_audit_events_status"),
    )
    op.create_index("idx_channel_outbound_audit_events_binding_time", "channel_outbound_audit_events", ["channel_binding_id", "occurred_at"])
    op.create_index("idx_channel_outbound_audit_events_delivery", "channel_outbound_audit_events", ["channel_delivery_event_id"])

    op.create_table(
        "channel_memory_gate_traces",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("channel_binding_id", postgresql.UUID, nullable=False),
        sa.Column("channel_message_event_id", postgresql.UUID, nullable=True),
        sa.Column("channel_memory_candidate_id", postgresql.UUID, nullable=True),
        sa.Column("memory_gate_decision", sa.Text(), nullable=False),
        sa.Column("memory_gate_status", sa.Text(), nullable=False, server_default=sa.text("'recorded'")),
        sa.Column("gate_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("safe_gate_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["channel_binding_id"], ["channel_bindings.id"]),
        sa.ForeignKeyConstraint(["channel_message_event_id"], ["channel_message_events.id"]),
        sa.ForeignKeyConstraint(["channel_memory_candidate_id"], ["channel_memory_candidates.id"]),
        ck("memory_gate_decision", MEMORY_GATE_DECISION_VALUES, "ck_channel_memory_gate_traces_decision"),
        ck("memory_gate_status", MEMORY_GATE_STATUS_VALUES, "ck_channel_memory_gate_traces_status"),
    )
    op.create_index("idx_channel_memory_gate_traces_binding_time", "channel_memory_gate_traces", ["channel_binding_id", "occurred_at"])
    op.create_index("idx_channel_memory_gate_traces_candidate", "channel_memory_gate_traces", ["channel_memory_candidate_id"])


def downgrade() -> None:
    op.drop_index("idx_channel_memory_gate_traces_candidate", table_name="channel_memory_gate_traces")
    op.drop_index("idx_channel_memory_gate_traces_binding_time", table_name="channel_memory_gate_traces")
    op.drop_table("channel_memory_gate_traces")

    op.drop_index("idx_channel_outbound_audit_events_delivery", table_name="channel_outbound_audit_events")
    op.drop_index("idx_channel_outbound_audit_events_binding_time", table_name="channel_outbound_audit_events")
    op.drop_table("channel_outbound_audit_events")

    op.drop_index("idx_channel_binding_status_events_binding_time", table_name="channel_binding_status_events")
    op.drop_table("channel_binding_status_events")

    op.drop_index("idx_channel_audit_logs_trace", table_name="channel_audit_logs")
    op.drop_index("idx_channel_audit_logs_binding_time", table_name="channel_audit_logs")
    op.drop_table("channel_audit_logs")

    op.drop_index("idx_channel_trace_events_trace_run", table_name="channel_trace_events")
    op.drop_index("idx_channel_trace_events_binding_type", table_name="channel_trace_events")
    op.drop_table("channel_trace_events")

    op.drop_index("idx_cre_phase6_trace_run", table_name="channel_revoke_events")
    op.drop_index("idx_cre_phase6_channel_binding", table_name="channel_revoke_events")
    op.drop_constraint("ck_cre_phase6_disables_candidates", "channel_revoke_events", type_="check")
    op.drop_constraint("ck_cre_phase6_clears_buffer", "channel_revoke_events", type_="check")
    op.drop_constraint("ck_cre_phase6_stops_checkins", "channel_revoke_events", type_="check")
    op.drop_constraint("fk_cre_phase6_trace_run", "channel_revoke_events", type_="foreignkey")
    op.drop_constraint("fk_cre_phase6_provider_bot", "channel_revoke_events", type_="foreignkey")
    op.drop_constraint("fk_cre_phase6_provider", "channel_revoke_events", type_="foreignkey")
    op.drop_constraint("fk_cre_phase6_channel_binding", "channel_revoke_events", type_="foreignkey")
    op.drop_column("channel_revoke_events", "disables_memory_candidates")
    op.drop_column("channel_revoke_events", "clears_ephemeral_buffer")
    op.drop_column("channel_revoke_events", "stops_checkins")
    op.drop_column("channel_revoke_events", "trace_run_id")
    op.drop_column("channel_revoke_events", "provider_bot_id")
    op.drop_column("channel_revoke_events", "provider_id")
    op.drop_column("channel_revoke_events", "channel_binding_id")
