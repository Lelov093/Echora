"""Personalized memory lifecycle state.

Revision ID: core_alg_02_memory
Revises: core_alg_01_feedback
Create Date: 2026-06-05 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "core_alg_02_memory"
down_revision: Union[str, Sequence[str], None] = "core_alg_01_feedback"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    columns = (
        sa.Column("confidence_prior_alpha", sa.Double(), nullable=False, server_default=sa.text("2.0")),
        sa.Column("confidence_prior_beta", sa.Double(), nullable=False, server_default=sa.text("2.0")),
        sa.Column("confidence_alpha", sa.Double(), nullable=False, server_default=sa.text("2.0")),
        sa.Column("confidence_beta", sa.Double(), nullable=False, server_default=sa.text("2.0")),
        sa.Column("successful_recall_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("growth_use_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("presence_use_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("repeated_topic_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("calibrated_positive_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("calibrated_helpful_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("calibrated_irrelevant_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("calibrated_outdated_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("calibrated_wrong_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("strength_anchor_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_maintenance_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "lifecycle_algorithm_version",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'core-memory-lifecycle-v1'"),
        ),
    )
    for column in columns:
        op.add_column("memories", column)

    op.create_check_constraint(
        "ck_memories_beta_confidence_positive",
        "memories",
        "confidence_prior_alpha > 0 AND confidence_prior_beta > 0 "
        "AND confidence_alpha > 0 AND confidence_beta > 0",
    )
    op.create_check_constraint(
        "ck_memories_lifecycle_counts_nonnegative",
        "memories",
        "successful_recall_count >= 0 AND growth_use_count >= 0 "
        "AND presence_use_count >= 0 AND repeated_topic_count >= 0 "
        "AND calibrated_positive_count >= 0 AND calibrated_helpful_count >= 0 "
        "AND calibrated_irrelevant_count >= 0 AND calibrated_outdated_count >= 0 "
        "AND calibrated_wrong_count >= 0",
    )
    op.create_index(
        "idx_memories_lifecycle_maintenance",
        "memories",
        ["companion_id", "state", "last_maintenance_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_memories_lifecycle_maintenance", table_name="memories")
    op.drop_constraint("ck_memories_lifecycle_counts_nonnegative", "memories", type_="check")
    op.drop_constraint("ck_memories_beta_confidence_positive", "memories", type_="check")
    for column in (
        "lifecycle_algorithm_version",
        "last_maintenance_at",
        "strength_anchor_at",
        "calibrated_wrong_count",
        "calibrated_outdated_count",
        "calibrated_irrelevant_count",
        "calibrated_helpful_count",
        "calibrated_positive_count",
        "repeated_topic_count",
        "presence_use_count",
        "growth_use_count",
        "successful_recall_count",
        "confidence_beta",
        "confidence_alpha",
        "confidence_prior_beta",
        "confidence_prior_alpha",
    ):
        op.execute(f"ALTER TABLE memories DROP COLUMN IF EXISTS {column}")
