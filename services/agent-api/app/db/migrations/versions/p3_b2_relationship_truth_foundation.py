"""P3-B2 Relationship candidate, posterior belief, and revision truth.

Revision ID: p3_b2_relationship_truth
Revises: p3_b1_memory_revision_events
Create Date: 2026-07-16 20:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "p3_b2_relationship_truth"
down_revision: Union[str, Sequence[str], None] = "p3_b1_memory_revision_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("relationship_states", sa.Column("revision", sa.Integer(), server_default="0", nullable=False))
    op.add_column("relationship_states", sa.Column("current_revision_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("relationship_states", sa.Column("belief_state_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False))
    op.add_column("relationship_states", sa.Column("last_evidence_at", sa.DateTime(timezone=True), nullable=True))
    op.create_check_constraint("ck_relationship_states_revision", "relationship_states", "revision >= 0")

    op.create_table(
        "relationship_candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trace_run_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(32), server_default="pending", nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("dimension_signals_json", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("source_message_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default="{}", nullable=False),
        sa.Column("source_memory_ids", postgresql.ARRAY(postgresql.UUID(as_uuid=True)), server_default="{}", nullable=False),
        sa.Column("evidence_quotes_json", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("extraction_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("validation_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("evidence_score", sa.Double(), server_default="0", nullable=False),
        sa.Column("confidence", sa.Double(), server_default="0", nullable=False),
        sa.Column("risk_level", sa.String(20), server_default="medium", nullable=False),
        sa.Column("requires_user_review", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("expected_state_revision", sa.Integer(), server_default="0", nullable=False),
        sa.Column("provider_name", sa.String(100), nullable=True),
        sa.Column("model_name", sa.String(200), nullable=True),
        sa.Column("algorithm_version", sa.String(100), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("committed_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_reason", sa.Text(), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_relationship_candidate_idempotency"),
        sa.CheckConstraint("status IN ('pending','committed','rejected','expired')", name="ck_relationship_candidate_status"),
        sa.CheckConstraint("evidence_score >= 0 AND evidence_score <= 1", name="ck_relationship_candidate_evidence"),
        sa.CheckConstraint("confidence >= 0 AND confidence <= 1", name="ck_relationship_candidate_confidence"),
        sa.CheckConstraint("risk_level IN ('low','medium','high')", name="ck_relationship_candidate_risk"),
        sa.CheckConstraint("expected_state_revision >= 0", name="ck_relationship_candidate_revision"),
    )
    op.create_index("idx_relationship_candidates_scope_status", "relationship_candidates", ["companion_id", "status", "created_at"])

    op.create_table(
        "relationship_state_revisions",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("relationship_state_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_candidate_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("previous_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("restored_from_revision_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(32), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("snapshot_before_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("snapshot_after_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("belief_before_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("belief_after_json", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("algorithm_version", sa.String(100), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["relationship_state_id"], ["relationship_states.id"]),
        sa.ForeignKeyConstraint(["source_candidate_id"], ["relationship_candidates.id"]),
        sa.ForeignKeyConstraint(["previous_revision_id"], ["relationship_state_revisions.id"]),
        sa.ForeignKeyConstraint(["restored_from_revision_id"], ["relationship_state_revisions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("relationship_state_id", "revision", name="uq_relationship_state_revision"),
        sa.CheckConstraint("revision >= 1", name="ck_relationship_state_revision_positive"),
        sa.CheckConstraint("operation IN ('committed','corrected','reverted')", name="ck_relationship_state_revision_operation"),
    )
    op.create_index("idx_relationship_state_revisions_scope", "relationship_state_revisions", ["companion_id", "relationship_state_id", "revision"])

    op.add_column("relationship_events", sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("relationship_events", sa.Column("state_revision_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("relationship_events", sa.Column("event_group_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("relationship_events", sa.Column("supersedes_event_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("relationship_events", sa.Column("operation", sa.String(32), server_default="committed", nullable=False))
    op.add_column("relationship_events", sa.Column("evidence_weight", sa.Double(), nullable=True))
    op.add_column("relationship_events", sa.Column("posterior_variance", sa.Double(), nullable=True))
    op.create_foreign_key("fk_relationship_events_candidate", "relationship_events", "relationship_candidates", ["candidate_id"], ["id"])
    op.create_foreign_key("fk_relationship_events_revision", "relationship_events", "relationship_state_revisions", ["state_revision_id"], ["id"])
    op.create_foreign_key("fk_relationship_events_supersedes", "relationship_events", "relationship_events", ["supersedes_event_id"], ["id"])
    op.create_check_constraint("ck_relationship_events_operation", "relationship_events", "operation IN ('committed','corrected','reverted')")
    op.create_check_constraint("ck_relationship_events_weight", "relationship_events", "evidence_weight IS NULL OR (evidence_weight >= 0 AND evidence_weight <= 1.5)")

    op.create_table(
        "companion_chronicle_summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("companion_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(32), server_default="active", nullable=False),
        sa.Column("title", sa.String(240), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("highlights_json", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("source_event_refs", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("generated_by_provider", sa.String(100), nullable=False),
        sa.Column("generated_by_model", sa.String(200), nullable=True),
        sa.Column("supersedes_summary_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("invalidation_reason", sa.Text(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["supersedes_summary_id"], ["companion_chronicle_summaries.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("companion_id", "version", name="uq_companion_chronicle_summary_version"),
        sa.CheckConstraint("version >= 1", name="ck_companion_chronicle_summary_version"),
        sa.CheckConstraint("status IN ('active','superseded','invalidated')", name="ck_companion_chronicle_summary_status"),
    )
    op.create_index("idx_companion_chronicle_summaries_scope", "companion_chronicle_summaries", ["companion_id", "status", "version"])


def downgrade() -> None:
    op.drop_index("idx_companion_chronicle_summaries_scope", table_name="companion_chronicle_summaries")
    op.drop_table("companion_chronicle_summaries")
    op.drop_constraint("ck_relationship_events_weight", "relationship_events", type_="check")
    op.drop_constraint("ck_relationship_events_operation", "relationship_events", type_="check")
    op.drop_constraint("fk_relationship_events_supersedes", "relationship_events", type_="foreignkey")
    op.drop_constraint("fk_relationship_events_revision", "relationship_events", type_="foreignkey")
    op.drop_constraint("fk_relationship_events_candidate", "relationship_events", type_="foreignkey")
    for column in ("posterior_variance", "evidence_weight", "operation", "supersedes_event_id", "event_group_id", "state_revision_id", "candidate_id"):
        op.drop_column("relationship_events", column)
    op.drop_index("idx_relationship_state_revisions_scope", table_name="relationship_state_revisions")
    op.drop_table("relationship_state_revisions")
    op.drop_index("idx_relationship_candidates_scope_status", table_name="relationship_candidates")
    op.drop_table("relationship_candidates")
    op.drop_constraint("ck_relationship_states_revision", "relationship_states", type_="check")
    for column in ("last_evidence_at", "belief_state_json", "current_revision_id", "revision"):
        op.drop_column("relationship_states", column)
