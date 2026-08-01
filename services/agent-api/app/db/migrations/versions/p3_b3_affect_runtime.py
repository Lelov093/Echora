"""P3-B3 first-class Companion affect runtime.

Revision ID: p3_b3_affect_runtime
Revises: p3_b2_relationship_truth
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p3_b3_affect_runtime"
down_revision = "p3_b2_relationship_truth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companion_affect_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companions.id"), nullable=False),
        sa.Column("valence", sa.Double(), server_default="0.08", nullable=False),
        sa.Column("arousal", sa.Double(), server_default="-0.08", nullable=False),
        sa.Column("home_valence", sa.Double(), server_default="0.08", nullable=False),
        sa.Column("home_arousal", sa.Double(), server_default="-0.08", nullable=False),
        sa.Column("half_life_hours", sa.Double(), server_default="18.0", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("current_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("last_transition_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expression_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("expression_intensity", sa.String(16), server_default="subtle", nullable=False),
        sa.Column("expression_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "companion_id", name="uq_companion_affect_scope"),
        sa.CheckConstraint("valence BETWEEN -1 AND 1 AND arousal BETWEEN -1 AND 1 AND home_valence BETWEEN -1 AND 1 AND home_arousal BETWEEN -1 AND 1", name="ck_companion_affect_state_range"),
        sa.CheckConstraint("half_life_hours BETWEEN 0.25 AND 168", name="ck_companion_affect_half_life"),
        sa.CheckConstraint("revision >= 0", name="ck_companion_affect_revision"),
        sa.CheckConstraint("expression_intensity IN ('off', 'subtle', 'balanced')", name="ck_companion_affect_expression_intensity"),
    )
    op.create_index("idx_companion_affect_state_scope", "companion_affect_states", ["companion_id", "updated_at"])
    op.create_table(
        "companion_affect_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companions.id"), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("conversations.id"), nullable=True),
        sa.Column("trace_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("source_message_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default="{}", nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("operation", sa.String(20), server_default="appraised", nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("evidence_quote", sa.Text(), nullable=False),
        sa.Column("appraisal_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("transition_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("extraction_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("validation_json", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("state_revision", sa.Integer(), nullable=False),
        sa.Column("supersedes_event_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companion_affect_events.id"), nullable=True),
        sa.Column("provider_name", sa.String(100), nullable=True),
        sa.Column("model_name", sa.String(200), nullable=True),
        sa.Column("algorithm_version", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False, unique=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('active', 'corrected', 'invalidated')", name="ck_companion_affect_event_status"),
        sa.CheckConstraint("operation IN ('appraised', 'corrected', 'invalidated')", name="ck_companion_affect_event_operation"),
        sa.CheckConstraint("state_revision > 0", name="ck_companion_affect_event_revision"),
    )
    op.create_index("idx_companion_affect_events_scope", "companion_affect_events", ["companion_id", "created_at"])
    op.create_foreign_key("fk_companion_affect_current_event", "companion_affect_states", "companion_affect_events", ["current_event_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_companion_affect_current_event", "companion_affect_states", type_="foreignkey")
    op.drop_index("idx_companion_affect_events_scope", table_name="companion_affect_events")
    op.drop_table("companion_affect_events")
    op.drop_index("idx_companion_affect_state_scope", table_name="companion_affect_states")
    op.drop_table("companion_affect_states")
