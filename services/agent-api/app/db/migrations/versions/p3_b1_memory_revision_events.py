"""Add lifecycle evidence types for versioned Saved Memory content.

Revision ID: p3_b1_memory_revision_events
Revises: p3_b1_memory_context_retention
Create Date: 2026-07-16 00:10:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "p3_b1_memory_revision_events"
down_revision: Union[str, Sequence[str], None] = "p3_b1_memory_context_retention"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

BASE_TYPES = (
    "created", "candidate_accepted", "candidate_edited", "candidate_merged",
    "reactivated", "strengthened", "weakened", "faded", "locked", "archived",
    "suppressed", "deleted", "confidence_updated", "half_life_updated",
    "abstraction_created", "abstraction_committed", "conflict_flagged", "outdated_flagged",
)
VERSION_TYPES = ("content_corrected", "content_merged", "content_restored")


def _constraint(values: tuple[str, ...]) -> str:
    return "event_type IN (" + ",".join(f"'{value}'" for value in values) + ")"


def upgrade() -> None:
    op.drop_constraint("memory_lifecycle_events_type_check", "memory_lifecycle_events", type_="check")
    op.create_check_constraint(
        "memory_lifecycle_events_type_check",
        "memory_lifecycle_events",
        _constraint(BASE_TYPES + VERSION_TYPES),
    )


def downgrade() -> None:
    op.drop_constraint("memory_lifecycle_events_type_check", "memory_lifecycle_events", type_="check")
    op.create_check_constraint(
        "memory_lifecycle_events_type_check",
        "memory_lifecycle_events",
        _constraint(BASE_TYPES),
    )
