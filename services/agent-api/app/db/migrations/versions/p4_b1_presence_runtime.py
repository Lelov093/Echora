"""P4-B1 durable Presence scheduler and delivery runtime.

Revision ID: p4_b1_presence_runtime
Revises: p3_b3_affect_runtime
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p4_b1_presence_runtime"
down_revision = "p3_b3_affect_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "presence_schedules",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companions.id"), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'paused'"), nullable=False),
        sa.Column("pause_reason", sa.Text()),
        sa.Column("destination_mode", sa.String(40), server_default=sa.text("'bound_conversation'"), nullable=False),
        sa.Column("bound_conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id")),
        sa.Column("latest_created_conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id")),
        sa.Column("timezone", sa.String(100), server_default=sa.text("'UTC'"), nullable=False),
        sa.Column("weekdays", postgresql.ARRAY(sa.Integer()), server_default=sa.text("'{0,1,2,3,4,5,6}'::integer[]"), nullable=False),
        sa.Column("timing_mode", sa.String(20), server_default=sa.text("'fixed'"), nullable=False),
        sa.Column("fixed_minute_of_day", sa.Integer(), server_default="1200", nullable=False),
        sa.Column("window_start_minute", sa.Integer(), server_default="1140", nullable=False),
        sa.Column("window_end_minute", sa.Integer(), server_default="1320", nullable=False),
        sa.Column("cadence_mode", sa.String(20), server_default=sa.text("'fixed'"), nullable=False),
        sa.Column("fixed_interval_minutes", sa.Integer(), server_default="1440", nullable=False),
        sa.Column("random_interval_min_minutes", sa.Integer(), server_default="1440", nullable=False),
        sa.Column("random_interval_max_minutes", sa.Integer(), server_default="4320", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("occurrence_sequence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("next_occurrence_at", sa.DateTime(timezone=True)),
        sa.Column("last_scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("last_delivered_at", sa.DateTime(timezone=True)),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "companion_id", name="uq_presence_schedule_scope"),
        sa.CheckConstraint("status IN ('active', 'paused')", name="ck_presence_schedule_status"),
        sa.CheckConstraint("destination_mode IN ('bound_conversation', 'new_conversation_per_delivery')", name="ck_presence_schedule_destination"),
        sa.CheckConstraint("timing_mode IN ('fixed', 'random_window')", name="ck_presence_schedule_timing"),
        sa.CheckConstraint("cadence_mode IN ('fixed', 'random_interval')", name="ck_presence_schedule_cadence"),
        sa.CheckConstraint("fixed_minute_of_day BETWEEN 0 AND 1439 AND window_start_minute BETWEEN 0 AND 1439 AND window_end_minute BETWEEN 0 AND 1439", name="ck_presence_schedule_minutes"),
        sa.CheckConstraint("fixed_interval_minutes BETWEEN 60 AND 525600", name="ck_presence_schedule_fixed_interval"),
        sa.CheckConstraint("random_interval_min_minutes BETWEEN 60 AND 525600 AND random_interval_max_minutes BETWEEN random_interval_min_minutes AND 525600", name="ck_presence_schedule_random_interval"),
        sa.CheckConstraint("revision > 0 AND occurrence_sequence >= 0", name="ck_presence_schedule_revision"),
    )
    op.create_index("idx_presence_schedule_due", "presence_schedules", ["status", "next_occurrence_at"])
    op.create_index("idx_presence_schedule_companion", "presence_schedules", ["companion_id"])

    op.create_table(
        "presence_schedule_occurrences",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("schedule_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("presence_schedules.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companions.id"), nullable=False),
        sa.Column("schedule_revision", sa.Integer(), nullable=False),
        sa.Column("sequence_no", sa.Integer(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("status", sa.String(24), server_default=sa.text("'scheduled'"), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("delivered_at", sa.DateTime(timezone=True)),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id")),
        sa.Column("presence_opportunity_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("presence_opportunities.id")),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("messages.id")),
        sa.Column("suppression_reason", sa.String(100)),
        sa.Column("error_code", sa.String(100)),
        sa.Column("error_summary", sa.Text()),
        sa.Column("random_draw_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("delivery_evidence_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schedule_id", "sequence_no", name="uq_presence_occurrence_sequence"),
        sa.CheckConstraint("status IN ('scheduled', 'claimed', 'retry_wait', 'delivered', 'suppressed', 'failed', 'expired', 'cancelled')", name="ck_presence_occurrence_status"),
        sa.CheckConstraint("schedule_revision > 0 AND sequence_no > 0 AND attempt_count >= 0", name="ck_presence_occurrence_counters"),
    )
    op.create_index("idx_presence_occurrence_due", "presence_schedule_occurrences", ["status", "scheduled_for", "lease_expires_at"])
    op.create_index("idx_presence_occurrence_schedule", "presence_schedule_occurrences", ["schedule_id", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_presence_occurrence_schedule", table_name="presence_schedule_occurrences")
    op.drop_index("idx_presence_occurrence_due", table_name="presence_schedule_occurrences")
    op.drop_table("presence_schedule_occurrences")
    op.drop_index("idx_presence_schedule_companion", table_name="presence_schedules")
    op.drop_index("idx_presence_schedule_due", table_name="presence_schedules")
    op.drop_table("presence_schedules")
