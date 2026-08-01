"""Add durable P5-B2 Room turn and per-Companion execution evidence.

Revision ID: p5_b2_room_turn_runtime
Revises: p5_b1_room_lifecycle_constraints
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p5_b2_room_turn_runtime"
down_revision = "p5_b1_room_lifecycle_constraints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companion_room_turns",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("co_presence_session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_message_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False, server_default="web"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="planning"),
        sa.Column("cancellation_requested", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("speaker_plan_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.ForeignKeyConstraint(["co_presence_session_id"], ["co_presence_sessions.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_message_id"], ["messages.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("co_presence_session_id", "idempotency_key", name="uq_room_turn_idempotency"),
        sa.CheckConstraint("status IN ('planning','running','completed','partial_failed','suppressed','failed','cancelled')", name="ck_room_turn_status"),
    )
    op.create_index("ix_room_turn_room_created", "companion_room_turns", ["co_presence_session_id", "created_at"])
    op.create_table(
        "companion_room_turn_steps",
        sa.Column("room_turn_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("participant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="planned"),
        sa.Column("selection_reason", sa.String(length=80), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trace_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("assistant_message_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("evidence_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("error_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("retry_available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["assistant_message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["participant_id"], ["co_presence_participants.id"]),
        sa.ForeignKeyConstraint(["room_turn_id"], ["companion_room_turns.id"]),
        sa.ForeignKeyConstraint(["trace_run_id"], ["trace_runs.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("room_turn_id", "companion_id", name="uq_room_turn_step_companion"),
        sa.CheckConstraint("status IN ('planned','running','completed','suppressed','failed','cancelled')", name="ck_room_turn_step_status"),
    )
    op.create_index("ix_room_turn_step_turn_ordinal", "companion_room_turn_steps", ["room_turn_id", "ordinal"])
    op.execute(sa.text(
        "UPDATE conversations SET metadata = jsonb_set("
        "jsonb_set(COALESCE(metadata, '{}'::jsonb), '{runtime_status}', '\"multi_companion_active\"'::jsonb), "
        "'{multi_companion_execution}', 'true'::jsonb) "
        "WHERE metadata->>'product_kind' = 'companion_room'"
    ))


def downgrade() -> None:
    op.execute(sa.text(
        "UPDATE conversations SET metadata = jsonb_set("
        "jsonb_set(COALESCE(metadata, '{}'::jsonb), '{runtime_status}', '\"foundation_only\"'::jsonb), "
        "'{multi_companion_execution}', 'false'::jsonb) "
        "WHERE metadata->>'product_kind' = 'companion_room'"
    ))
    op.drop_index("ix_room_turn_step_turn_ordinal", table_name="companion_room_turn_steps")
    op.drop_table("companion_room_turn_steps")
    op.drop_index("ix_room_turn_room_created", table_name="companion_room_turns")
    op.drop_table("companion_room_turns")
