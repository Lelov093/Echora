"""phase6_03_channel_message_delivery_event_schema

Revision ID: p6_03_channel_events
Revises: p6_02_channel_identity
Create Date: 2026-06-03 00:00:00.000000

Create Phase 6 Channel Message / Delivery / Webhook / Rate Limit / Failure
event schema. External channel messages remain ephemeral by default and raw
payload storage is disallowed.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p6_03_channel_events"
down_revision: Union[str, Sequence[str], None] = "p6_02_channel_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


WEBHOOK_STATUS_VALUES = ("received", "normalized", "ignored", "redacted", "failed")
WEBHOOK_EVENT_TYPE_VALUES = ("message_create", "message_update", "message_delete", "interaction", "system")
DELIVERY_STATUS_VALUES = ("queued", "sent", "suppressed", "failed", "rate_limited")
DELIVERY_MODE_VALUES = ("reply_only", "user_approved", "low_frequency_checkin")
RATE_LIMIT_STATUS_VALUES = ("active", "resolved")
FAILURE_TYPE_VALUES = ("provider_error", "permission_denied", "boundary_suppressed", "rate_limited", "unknown")
FAILURE_STATUS_VALUES = ("recorded", "resolved", "ignored")


def ck(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=name)


def jsonb_default() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.add_column("channel_message_events", sa.Column("channel_binding_id", postgresql.UUID, nullable=True))
    op.add_column("channel_message_events", sa.Column("provider_id", postgresql.UUID, nullable=True))
    op.add_column("channel_message_events", sa.Column("provider_bot_id", postgresql.UUID, nullable=True))
    op.add_column("channel_message_events", sa.Column("trace_run_id", postgresql.UUID, nullable=True))
    op.add_column("channel_message_events", sa.Column("external_message_ref_hash", sa.Text(), nullable=True))
    op.add_column("channel_message_events", sa.Column("external_conversation_ref_hash", sa.Text(), nullable=True))
    op.add_column("channel_message_events", sa.Column("idempotency_key", sa.Text(), nullable=True))
    op.add_column(
        "channel_message_events",
        sa.Column("payload_is_ephemeral", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "channel_message_events",
        sa.Column("raw_payload_storage_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "channel_message_events",
        sa.Column(
            "safe_payload_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=jsonb_default(),
        ),
    )

    op.create_foreign_key("fk_cme_phase6_channel_binding", "channel_message_events", "channel_bindings", ["channel_binding_id"], ["id"])
    op.create_foreign_key("fk_cme_phase6_provider", "channel_message_events", "channel_providers", ["provider_id"], ["id"])
    op.create_foreign_key("fk_cme_phase6_provider_bot", "channel_message_events", "channel_bot_registries", ["provider_bot_id"], ["id"])
    op.create_foreign_key("fk_cme_phase6_trace_run", "channel_message_events", "trace_runs", ["trace_run_id"], ["id"])
    op.create_check_constraint("ck_cme_phase6_payload_ephemeral", "channel_message_events", "payload_is_ephemeral = true")
    op.create_check_constraint("ck_cme_phase6_no_raw_payload", "channel_message_events", "raw_payload_storage_allowed = false")
    op.create_index("idx_cme_phase6_binding_direction", "channel_message_events", ["channel_binding_id", "message_direction", "occurred_at"])
    op.create_index("idx_cme_phase6_provider_bot", "channel_message_events", ["provider_id", "provider_bot_id", "occurred_at"])
    op.create_index("idx_cme_phase6_trace_run", "channel_message_events", ["trace_run_id"])

    op.create_table(
        "channel_webhook_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider_id", postgresql.UUID, nullable=False),
        sa.Column("provider_bot_id", postgresql.UUID, nullable=True),
        sa.Column("channel_binding_id", postgresql.UUID, nullable=True),
        sa.Column("channel_message_event_id", postgresql.UUID, nullable=True),
        sa.Column("webhook_event_type", sa.Text(), nullable=False),
        sa.Column("webhook_status", sa.Text(), nullable=False, server_default=sa.text("'received'")),
        sa.Column("external_event_ref_hash", sa.Text(), nullable=True),
        sa.Column("payload_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("raw_payload_storage_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("safe_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["provider_id"], ["channel_providers.id"]),
        sa.ForeignKeyConstraint(["provider_bot_id"], ["channel_bot_registries.id"]),
        sa.ForeignKeyConstraint(["channel_binding_id"], ["channel_bindings.id"]),
        sa.ForeignKeyConstraint(["channel_message_event_id"], ["channel_message_events.id"]),
        ck("webhook_event_type", WEBHOOK_EVENT_TYPE_VALUES, "ck_channel_webhook_events_type"),
        ck("webhook_status", WEBHOOK_STATUS_VALUES, "ck_channel_webhook_events_status"),
        sa.CheckConstraint("raw_payload_storage_allowed = false", name="ck_channel_webhook_events_no_raw_payload"),
    )
    op.create_index("idx_channel_webhook_events_provider_status", "channel_webhook_events", ["provider_id", "webhook_status"])
    op.create_index("idx_channel_webhook_events_binding_received", "channel_webhook_events", ["channel_binding_id", "received_at"])

    op.create_table(
        "channel_delivery_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("channel_binding_id", postgresql.UUID, nullable=False),
        sa.Column("channel_message_event_id", postgresql.UUID, nullable=True),
        sa.Column("provider_id", postgresql.UUID, nullable=False),
        sa.Column("provider_bot_id", postgresql.UUID, nullable=True),
        sa.Column("trace_run_id", postgresql.UUID, nullable=True),
        sa.Column("delivery_status", sa.Text(), nullable=False, server_default=sa.text("'queued'")),
        sa.Column("delivery_mode", sa.Text(), nullable=False, server_default=sa.text("'reply_only'")),
        sa.Column("delivery_attempt", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("external_delivery_ref_hash", sa.Text(), nullable=True),
        sa.Column("delivery_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("raw_payload_storage_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("safe_delivery_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["channel_binding_id"], ["channel_bindings.id"]),
        sa.ForeignKeyConstraint(["channel_message_event_id"], ["channel_message_events.id"]),
        sa.ForeignKeyConstraint(["provider_id"], ["channel_providers.id"]),
        sa.ForeignKeyConstraint(["provider_bot_id"], ["channel_bot_registries.id"]),
        sa.ForeignKeyConstraint(["trace_run_id"], ["trace_runs.id"]),
        ck("delivery_status", DELIVERY_STATUS_VALUES, "ck_channel_delivery_events_status"),
        ck("delivery_mode", DELIVERY_MODE_VALUES, "ck_channel_delivery_events_mode"),
        sa.CheckConstraint("delivery_attempt >= 1", name="ck_channel_delivery_events_attempt_positive"),
        sa.CheckConstraint("raw_payload_storage_allowed = false", name="ck_channel_delivery_events_no_raw_payload"),
    )
    op.create_index("idx_channel_delivery_events_binding_status", "channel_delivery_events", ["channel_binding_id", "delivery_status"])
    op.create_index("idx_channel_delivery_events_provider_bot", "channel_delivery_events", ["provider_id", "provider_bot_id"])
    op.create_index("idx_channel_delivery_events_trace_run", "channel_delivery_events", ["trace_run_id"])

    op.create_table(
        "channel_rate_limit_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider_id", postgresql.UUID, nullable=False),
        sa.Column("provider_bot_id", postgresql.UUID, nullable=True),
        sa.Column("channel_binding_id", postgresql.UUID, nullable=True),
        sa.Column("rate_limit_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("retry_after_seconds", sa.Integer(), nullable=True),
        sa.Column("limit_scope_hash", sa.Text(), nullable=True),
        sa.Column("safe_rate_limit_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["provider_id"], ["channel_providers.id"]),
        sa.ForeignKeyConstraint(["provider_bot_id"], ["channel_bot_registries.id"]),
        sa.ForeignKeyConstraint(["channel_binding_id"], ["channel_bindings.id"]),
        ck("rate_limit_status", RATE_LIMIT_STATUS_VALUES, "ck_channel_rate_limit_events_status"),
        sa.CheckConstraint("retry_after_seconds IS NULL OR retry_after_seconds >= 0", name="ck_channel_rate_limit_events_retry_nonnegative"),
    )
    op.create_index("idx_channel_rate_limit_events_provider_status", "channel_rate_limit_events", ["provider_id", "rate_limit_status"])
    op.create_index("idx_channel_rate_limit_events_binding_status", "channel_rate_limit_events", ["channel_binding_id", "rate_limit_status"])

    op.create_table(
        "channel_failure_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider_id", postgresql.UUID, nullable=False),
        sa.Column("provider_bot_id", postgresql.UUID, nullable=True),
        sa.Column("channel_binding_id", postgresql.UUID, nullable=True),
        sa.Column("channel_message_event_id", postgresql.UUID, nullable=True),
        sa.Column("channel_delivery_event_id", postgresql.UUID, nullable=True),
        sa.Column("failure_type", sa.Text(), nullable=False, server_default=sa.text("'unknown'")),
        sa.Column("failure_status", sa.Text(), nullable=False, server_default=sa.text("'recorded'")),
        sa.Column("safe_error_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("safe_error_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["provider_id"], ["channel_providers.id"]),
        sa.ForeignKeyConstraint(["provider_bot_id"], ["channel_bot_registries.id"]),
        sa.ForeignKeyConstraint(["channel_binding_id"], ["channel_bindings.id"]),
        sa.ForeignKeyConstraint(["channel_message_event_id"], ["channel_message_events.id"]),
        sa.ForeignKeyConstraint(["channel_delivery_event_id"], ["channel_delivery_events.id"]),
        ck("failure_type", FAILURE_TYPE_VALUES, "ck_channel_failure_events_type"),
        ck("failure_status", FAILURE_STATUS_VALUES, "ck_channel_failure_events_status"),
    )
    op.create_index("idx_channel_failure_events_provider_status", "channel_failure_events", ["provider_id", "failure_status"])
    op.create_index("idx_channel_failure_events_binding_status", "channel_failure_events", ["channel_binding_id", "failure_status"])
    op.create_index("idx_channel_failure_events_message", "channel_failure_events", ["channel_message_event_id"])
    op.create_index("idx_channel_failure_events_delivery", "channel_failure_events", ["channel_delivery_event_id"])


def downgrade() -> None:
    op.drop_index("idx_channel_failure_events_delivery", table_name="channel_failure_events")
    op.drop_index("idx_channel_failure_events_message", table_name="channel_failure_events")
    op.drop_index("idx_channel_failure_events_binding_status", table_name="channel_failure_events")
    op.drop_index("idx_channel_failure_events_provider_status", table_name="channel_failure_events")
    op.drop_table("channel_failure_events")

    op.drop_index("idx_channel_rate_limit_events_binding_status", table_name="channel_rate_limit_events")
    op.drop_index("idx_channel_rate_limit_events_provider_status", table_name="channel_rate_limit_events")
    op.drop_table("channel_rate_limit_events")

    op.drop_index("idx_channel_delivery_events_trace_run", table_name="channel_delivery_events")
    op.drop_index("idx_channel_delivery_events_provider_bot", table_name="channel_delivery_events")
    op.drop_index("idx_channel_delivery_events_binding_status", table_name="channel_delivery_events")
    op.drop_table("channel_delivery_events")

    op.drop_index("idx_channel_webhook_events_binding_received", table_name="channel_webhook_events")
    op.drop_index("idx_channel_webhook_events_provider_status", table_name="channel_webhook_events")
    op.drop_table("channel_webhook_events")

    op.drop_index("idx_cme_phase6_trace_run", table_name="channel_message_events")
    op.drop_index("idx_cme_phase6_provider_bot", table_name="channel_message_events")
    op.drop_index("idx_cme_phase6_binding_direction", table_name="channel_message_events")
    op.drop_constraint("ck_cme_phase6_no_raw_payload", "channel_message_events", type_="check")
    op.drop_constraint("ck_cme_phase6_payload_ephemeral", "channel_message_events", type_="check")
    op.drop_constraint("fk_cme_phase6_trace_run", "channel_message_events", type_="foreignkey")
    op.drop_constraint("fk_cme_phase6_provider_bot", "channel_message_events", type_="foreignkey")
    op.drop_constraint("fk_cme_phase6_provider", "channel_message_events", type_="foreignkey")
    op.drop_constraint("fk_cme_phase6_channel_binding", "channel_message_events", type_="foreignkey")
    op.drop_column("channel_message_events", "safe_payload_json")
    op.drop_column("channel_message_events", "raw_payload_storage_allowed")
    op.drop_column("channel_message_events", "payload_is_ephemeral")
    op.drop_column("channel_message_events", "idempotency_key")
    op.drop_column("channel_message_events", "external_conversation_ref_hash")
    op.drop_column("channel_message_events", "external_message_ref_hash")
    op.drop_column("channel_message_events", "trace_run_id")
    op.drop_column("channel_message_events", "provider_bot_id")
    op.drop_column("channel_message_events", "provider_id")
    op.drop_column("channel_message_events", "channel_binding_id")
