"""Expand safe user-state signal types for continuous EWMA state.

Revision ID: core_alg_03_user_state
Revises: core_alg_02_memory
Create Date: 2026-06-05 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "core_alg_03_user_state"
down_revision: Union[str, Sequence[str], None] = "core_alg_02_memory"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BASE_SIGNAL_TYPES = (
    "project_activity",
    "creative_activity",
    "presence_acceptance",
    "presence_dismissal",
    "memory_review_activity",
    "growth_review_activity",
    "continuity_need",
    "recent_confusion",
    "recent_satisfaction",
)
EXPANDED_SIGNAL_TYPES = (
    *BASE_SIGNAL_TYPES,
    "interaction_acceptance",
    "focus_load",
)


def _constraint(values: tuple[str, ...]) -> str:
    joined = ", ".join(f"'{value}'" for value in values)
    return f"signal_type IN ({joined})"


def upgrade() -> None:
    op.drop_constraint(
        "user_state_snapshots_signal_type_check",
        "user_state_snapshots",
        type_="check",
    )
    op.create_check_constraint(
        "user_state_snapshots_signal_type_check",
        "user_state_snapshots",
        _constraint(EXPANDED_SIGNAL_TYPES),
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM user_state_snapshots "
        "WHERE signal_type IN ('interaction_acceptance', 'focus_load')"
    )
    op.drop_constraint(
        "user_state_snapshots_signal_type_check",
        "user_state_snapshots",
        type_="check",
    )
    op.create_check_constraint(
        "user_state_snapshots_signal_type_check",
        "user_state_snapshots",
        _constraint(BASE_SIGNAL_TYPES),
    )
