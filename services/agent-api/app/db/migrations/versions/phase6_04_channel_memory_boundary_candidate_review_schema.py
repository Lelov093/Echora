"""phase6_04_channel_memory_boundary_candidate_review_schema

Revision ID: p6_04_channel_memory
Revises: p6_03_channel_events
Create Date: 2026-06-03 00:00:00.000000

Create Phase 6 Channel Memory Boundary / Ephemeral Buffer / Candidate /
Review schema. External channel content is ephemeral by default and can only
enter long-term memory through review-gated candidates.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "p6_04_channel_memory"
down_revision: Union[str, Sequence[str], None] = "p6_03_channel_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BUFFER_STATUS_VALUES = ("active", "expired", "cleared", "redacted")
BUFFER_ITEM_STATUS_VALUES = ("active", "expired", "candidate_created", "redacted", "cleared")
CANDIDATE_STATUS_VALUES = ("pending_review", "approved", "rejected", "redacted", "committed")
TARGET_MEMORY_SCOPE_VALUES = ("companion_private", "shared_episodic", "user_global_summary")
REVIEW_DECISION_VALUES = ("pending", "approved", "rejected", "redacted", "needs_changes")
REDACTION_SCOPE_VALUES = ("buffer", "buffer_item", "message_event", "memory_candidate", "review")
REDACTION_STATUS_VALUES = ("requested", "applied", "failed")


def ck(column: str, values: tuple[str, ...], name: str) -> sa.CheckConstraint:
    joined = ", ".join(f"'{value}'" for value in values)
    return sa.CheckConstraint(f"{column} IN ({joined})", name=name)


def jsonb_default() -> sa.TextClause:
    return sa.text("'{}'::jsonb")


def upgrade() -> None:
    op.add_column("channel_memory_boundary_policies", sa.Column("channel_binding_id", postgresql.UUID, nullable=True))
    op.add_column("channel_memory_boundary_policies", sa.Column("provider_id", postgresql.UUID, nullable=True))
    op.add_column(
        "channel_memory_boundary_policies",
        sa.Column("ephemeral_by_default", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "channel_memory_boundary_policies",
        sa.Column("review_required_for_memory_write", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column(
        "channel_memory_boundary_policies",
        sa.Column("auto_write_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_foreign_key(
        "fk_cmbp_phase6_channel_binding",
        "channel_memory_boundary_policies",
        "channel_bindings",
        ["channel_binding_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_cmbp_phase6_provider",
        "channel_memory_boundary_policies",
        "channel_providers",
        ["provider_id"],
        ["id"],
    )
    op.create_check_constraint("ck_cmbp_phase6_ephemeral_default", "channel_memory_boundary_policies", "ephemeral_by_default = true")
    op.create_check_constraint(
        "ck_cmbp_phase6_review_required",
        "channel_memory_boundary_policies",
        "review_required_for_memory_write = true",
    )
    op.create_check_constraint("ck_cmbp_phase6_no_auto_write", "channel_memory_boundary_policies", "auto_write_allowed = false")
    op.create_index("idx_cmbp_phase6_channel_binding", "channel_memory_boundary_policies", ["channel_binding_id"])
    op.create_index("idx_cmbp_phase6_provider", "channel_memory_boundary_policies", ["provider_id"])

    op.create_table(
        "channel_ephemeral_buffers",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("channel_binding_id", postgresql.UUID, nullable=False),
        sa.Column("provider_id", postgresql.UUID, nullable=False),
        sa.Column("provider_bot_id", postgresql.UUID, nullable=True),
        sa.Column("buffer_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("retention_seconds", sa.Integer(), nullable=False, server_default=sa.text("86400")),
        sa.Column("raw_payload_storage_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("memory_candidate_generation_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("safe_buffer_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("buffer_policy_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["channel_binding_id"], ["channel_bindings.id"]),
        sa.ForeignKeyConstraint(["provider_id"], ["channel_providers.id"]),
        sa.ForeignKeyConstraint(["provider_bot_id"], ["channel_bot_registries.id"]),
        ck("buffer_status", BUFFER_STATUS_VALUES, "ck_channel_ephemeral_buffers_status"),
        sa.CheckConstraint("retention_seconds >= 0", name="ck_channel_ephemeral_buffers_retention_nonnegative"),
        sa.CheckConstraint("raw_payload_storage_allowed = false", name="ck_channel_ephemeral_buffers_no_raw_payload"),
    )
    op.create_index("idx_channel_ephemeral_buffers_binding_status", "channel_ephemeral_buffers", ["channel_binding_id", "buffer_status"])
    op.create_index("idx_channel_ephemeral_buffers_companion_status", "channel_ephemeral_buffers", ["companion_id", "buffer_status"])

    op.create_table(
        "channel_ephemeral_buffer_items",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("channel_ephemeral_buffer_id", postgresql.UUID, nullable=False),
        sa.Column("channel_message_event_id", postgresql.UUID, nullable=True),
        sa.Column("buffer_item_status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("safe_content_summary", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("salience_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("raw_payload_storage_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("long_term_memory_written", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("safe_item_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["channel_ephemeral_buffer_id"], ["channel_ephemeral_buffers.id"]),
        sa.ForeignKeyConstraint(["channel_message_event_id"], ["channel_message_events.id"]),
        ck("buffer_item_status", BUFFER_ITEM_STATUS_VALUES, "ck_channel_ephemeral_buffer_items_status"),
        sa.CheckConstraint("salience_score >= 0 AND salience_score <= 1", name="ck_channel_ephemeral_buffer_items_salience"),
        sa.CheckConstraint("raw_payload_storage_allowed = false", name="ck_channel_ephemeral_buffer_items_no_raw_payload"),
        sa.CheckConstraint("long_term_memory_written = false", name="ck_channel_ephemeral_buffer_items_no_direct_memory_write"),
    )
    op.create_index(
        "idx_channel_ephemeral_buffer_items_buffer_status",
        "channel_ephemeral_buffer_items",
        ["channel_ephemeral_buffer_id", "buffer_item_status"],
    )
    op.create_index("idx_channel_ephemeral_buffer_items_message", "channel_ephemeral_buffer_items", ["channel_message_event_id"])

    op.create_table(
        "channel_memory_candidates",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("companion_id", postgresql.UUID, nullable=False),
        sa.Column("channel_binding_id", postgresql.UUID, nullable=False),
        sa.Column("provider_id", postgresql.UUID, nullable=False),
        sa.Column("provider_bot_id", postgresql.UUID, nullable=True),
        sa.Column("channel_message_event_id", postgresql.UUID, nullable=True),
        sa.Column("channel_ephemeral_buffer_item_id", postgresql.UUID, nullable=True),
        sa.Column("candidate_status", sa.Text(), nullable=False, server_default=sa.text("'pending_review'")),
        sa.Column("target_memory_scope", sa.Text(), nullable=False, server_default=sa.text("'companion_private'")),
        sa.Column("candidate_summary", sa.Text(), nullable=False),
        sa.Column("suggested_memory_content", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("salience_score", sa.Float(), nullable=False, server_default=sa.text("0")),
        sa.Column("requires_user_review", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_commit_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("raw_payload_storage_allowed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("safe_evidence_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["companion_id"], ["companions.id"]),
        sa.ForeignKeyConstraint(["channel_binding_id"], ["channel_bindings.id"]),
        sa.ForeignKeyConstraint(["provider_id"], ["channel_providers.id"]),
        sa.ForeignKeyConstraint(["provider_bot_id"], ["channel_bot_registries.id"]),
        sa.ForeignKeyConstraint(["channel_message_event_id"], ["channel_message_events.id"]),
        sa.ForeignKeyConstraint(["channel_ephemeral_buffer_item_id"], ["channel_ephemeral_buffer_items.id"]),
        ck("candidate_status", CANDIDATE_STATUS_VALUES, "ck_channel_memory_candidates_status"),
        ck("target_memory_scope", TARGET_MEMORY_SCOPE_VALUES, "ck_channel_memory_candidates_target_scope"),
        sa.CheckConstraint("salience_score >= 0 AND salience_score <= 1", name="ck_channel_memory_candidates_salience"),
        sa.CheckConstraint("requires_user_review = true", name="ck_channel_memory_candidates_review_required"),
        sa.CheckConstraint("auto_commit_allowed = false", name="ck_channel_memory_candidates_no_auto_commit"),
        sa.CheckConstraint("raw_payload_storage_allowed = false", name="ck_channel_memory_candidates_no_raw_payload"),
    )
    op.create_index("idx_channel_memory_candidates_binding_status", "channel_memory_candidates", ["channel_binding_id", "candidate_status"])
    op.create_index("idx_channel_memory_candidates_companion_status", "channel_memory_candidates", ["companion_id", "candidate_status"])
    op.create_index("idx_channel_memory_candidates_message", "channel_memory_candidates", ["channel_message_event_id"])

    op.create_table(
        "channel_memory_reviews",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("channel_memory_candidate_id", postgresql.UUID, nullable=False),
        sa.Column("review_decision", sa.Text(), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("target_memory_id", postgresql.UUID, nullable=True),
        sa.Column("review_notes", sa.Text(), nullable=True),
        sa.Column("memory_write_allowed_after_review", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("safe_review_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["channel_memory_candidate_id"], ["channel_memory_candidates.id"]),
        sa.ForeignKeyConstraint(["target_memory_id"], ["memories.id"]),
        ck("review_decision", REVIEW_DECISION_VALUES, "ck_channel_memory_reviews_decision"),
        sa.CheckConstraint(
            "memory_write_allowed_after_review = false OR review_decision = 'approved'",
            name="ck_channel_memory_reviews_write_requires_approval",
        ),
    )
    op.create_index("idx_channel_memory_reviews_candidate", "channel_memory_reviews", ["channel_memory_candidate_id"])
    op.create_index("idx_channel_memory_reviews_user_decision", "channel_memory_reviews", ["user_id", "review_decision"])

    op.create_table(
        "channel_context_redaction_events",
        sa.Column("id", postgresql.UUID, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", postgresql.UUID, nullable=False),
        sa.Column("channel_binding_id", postgresql.UUID, nullable=True),
        sa.Column("channel_message_event_id", postgresql.UUID, nullable=True),
        sa.Column("channel_ephemeral_buffer_item_id", postgresql.UUID, nullable=True),
        sa.Column("channel_memory_candidate_id", postgresql.UUID, nullable=True),
        sa.Column("redaction_scope", sa.Text(), nullable=False),
        sa.Column("redaction_status", sa.Text(), nullable=False, server_default=sa.text("'requested'")),
        sa.Column("redaction_reason", sa.Text(), nullable=True),
        sa.Column("safe_redaction_payload_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=jsonb_default()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["channel_binding_id"], ["channel_bindings.id"]),
        sa.ForeignKeyConstraint(["channel_message_event_id"], ["channel_message_events.id"]),
        sa.ForeignKeyConstraint(["channel_ephemeral_buffer_item_id"], ["channel_ephemeral_buffer_items.id"]),
        sa.ForeignKeyConstraint(["channel_memory_candidate_id"], ["channel_memory_candidates.id"]),
        ck("redaction_scope", REDACTION_SCOPE_VALUES, "ck_channel_context_redaction_events_scope"),
        ck("redaction_status", REDACTION_STATUS_VALUES, "ck_channel_context_redaction_events_status"),
    )
    op.create_index("idx_channel_context_redaction_binding", "channel_context_redaction_events", ["channel_binding_id"])
    op.create_index("idx_channel_context_redaction_candidate", "channel_context_redaction_events", ["channel_memory_candidate_id"])


def downgrade() -> None:
    op.drop_index("idx_channel_context_redaction_candidate", table_name="channel_context_redaction_events")
    op.drop_index("idx_channel_context_redaction_binding", table_name="channel_context_redaction_events")
    op.drop_table("channel_context_redaction_events")

    op.drop_index("idx_channel_memory_reviews_user_decision", table_name="channel_memory_reviews")
    op.drop_index("idx_channel_memory_reviews_candidate", table_name="channel_memory_reviews")
    op.drop_table("channel_memory_reviews")

    op.drop_index("idx_channel_memory_candidates_message", table_name="channel_memory_candidates")
    op.drop_index("idx_channel_memory_candidates_companion_status", table_name="channel_memory_candidates")
    op.drop_index("idx_channel_memory_candidates_binding_status", table_name="channel_memory_candidates")
    op.drop_table("channel_memory_candidates")

    op.drop_index("idx_channel_ephemeral_buffer_items_message", table_name="channel_ephemeral_buffer_items")
    op.drop_index("idx_channel_ephemeral_buffer_items_buffer_status", table_name="channel_ephemeral_buffer_items")
    op.drop_table("channel_ephemeral_buffer_items")

    op.drop_index("idx_channel_ephemeral_buffers_companion_status", table_name="channel_ephemeral_buffers")
    op.drop_index("idx_channel_ephemeral_buffers_binding_status", table_name="channel_ephemeral_buffers")
    op.drop_table("channel_ephemeral_buffers")

    op.drop_index("idx_cmbp_phase6_provider", table_name="channel_memory_boundary_policies")
    op.drop_index("idx_cmbp_phase6_channel_binding", table_name="channel_memory_boundary_policies")
    op.drop_constraint("ck_cmbp_phase6_no_auto_write", "channel_memory_boundary_policies", type_="check")
    op.drop_constraint("ck_cmbp_phase6_review_required", "channel_memory_boundary_policies", type_="check")
    op.drop_constraint("ck_cmbp_phase6_ephemeral_default", "channel_memory_boundary_policies", type_="check")
    op.drop_constraint("fk_cmbp_phase6_provider", "channel_memory_boundary_policies", type_="foreignkey")
    op.drop_constraint("fk_cmbp_phase6_channel_binding", "channel_memory_boundary_policies", type_="foreignkey")
    op.drop_column("channel_memory_boundary_policies", "auto_write_allowed")
    op.drop_column("channel_memory_boundary_policies", "review_required_for_memory_write")
    op.drop_column("channel_memory_boundary_policies", "ephemeral_by_default")
    op.drop_column("channel_memory_boundary_policies", "provider_id")
    op.drop_column("channel_memory_boundary_policies", "channel_binding_id")
