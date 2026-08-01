"""Add bounded memory hierarchy and graph provenance fields.

Revision ID: core_alg_04_memory_graph
Revises: core_alg_03_user_state
Create Date: 2026-06-05 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "core_alg_04_memory_graph"
down_revision: Union[str, Sequence[str], None] = "core_alg_03_user_state"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


MEMORY_LAYERS = (
    "user_global",
    "companion_private",
    "relationship",
    "shared_episodic",
    "project_context",
    "session_context",
)
MUTUAL_PRESENCE_ACTIONS = (
    "queue",
    "invite_scene",
    "defer",
    "silence",
    "review_required",
    "no_show",
    "hub",
)
LEGACY_MUTUAL_PRESENCE_ACTIONS = (
    "queue",
    "invite_scene",
    "defer",
    "silence",
    "review_required",
)


def upgrade() -> None:
    op.drop_constraint(
        "ck_mppr_action",
        "mutual_presence_policy_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_mppr_action",
        "mutual_presence_policy_runs",
        "selected_action IN ("
        + ", ".join(f"'{value}'" for value in MUTUAL_PRESENCE_ACTIONS)
        + ")",
    )

    op.add_column(
        "memories",
        sa.Column(
            "memory_layer",
            sa.Text(),
            nullable=False,
            server_default="companion_private",
        ),
    )
    op.create_check_constraint(
        "ck_memories_memory_layer",
        "memories",
        "memory_layer IN ("
        + ", ".join(f"'{value}'" for value in MEMORY_LAYERS)
        + ")",
    )
    op.execute(
        "UPDATE memories SET memory_layer = 'relationship' "
        "WHERE memory_scope_type = 'relationship'"
    )
    op.execute(
        "UPDATE memories SET memory_layer = 'shared_episodic' "
        "WHERE shared_memory_id IS NOT NULL OR memory_scope_type = 'shared_episodic'"
    )
    op.execute(
        "UPDATE memories SET memory_layer = 'project_context' "
        "WHERE metadata ? 'project_id'"
    )
    op.execute(
        "UPDATE memories SET memory_layer = 'session_context' "
        "WHERE conversation_id IS NOT NULL OR "
        "metadata ?| ARRAY['realtime_session_id', 'co_presence_session_id', "
        "'shared_scene_id', 'channel_id']"
    )
    op.create_index(
        "idx_memories_companion_layer_state",
        "memories",
        ["companion_id", "memory_layer", "state"],
    )

    op.add_column(
        "memory_edges",
        sa.Column(
            "edge_source",
            sa.Text(),
            nullable=False,
            server_default="manual",
        ),
    )
    op.add_column(
        "memory_edges",
        sa.Column(
            "confidence",
            sa.Double(),
            nullable=False,
            server_default=sa.text("0.5"),
        ),
    )
    op.create_check_constraint(
        "ck_memory_edges_confidence",
        "memory_edges",
        "confidence BETWEEN 0 AND 1",
    )
    op.create_index(
        "idx_memory_edges_companion_source",
        "memory_edges",
        ["companion_id", "source_memory_id"],
    )
    op.create_index(
        "idx_memory_edges_companion_target",
        "memory_edges",
        ["companion_id", "target_memory_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_memory_edges_companion_target", table_name="memory_edges")
    op.drop_index("idx_memory_edges_companion_source", table_name="memory_edges")
    op.drop_constraint(
        "ck_memory_edges_confidence",
        "memory_edges",
        type_="check",
    )
    op.drop_column("memory_edges", "confidence")
    op.drop_column("memory_edges", "edge_source")

    op.drop_index("idx_memories_companion_layer_state", table_name="memories")
    op.drop_constraint("ck_memories_memory_layer", "memories", type_="check")
    op.drop_column("memories", "memory_layer")

    op.drop_constraint(
        "ck_mppr_action",
        "mutual_presence_policy_runs",
        type_="check",
    )
    op.create_check_constraint(
        "ck_mppr_action",
        "mutual_presence_policy_runs",
        "selected_action IN ("
        + ", ".join(
            f"'{value}'" for value in LEGACY_MUTUAL_PRESENCE_ACTIONS
        )
        + ")",
    )
