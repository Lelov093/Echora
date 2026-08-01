"""Allow product Room sources and durable membership lifecycle states.

Revision ID: p5_b1_room_lifecycle_constraints
Revises: p5_b1_room_membership_backfill
"""

from alembic import op
import sqlalchemy as sa


revision = "p5_b1_room_lifecycle_constraints"
down_revision = "p5_b1_room_membership_backfill"
branch_labels = None
depends_on = None


_LEGACY_SESSION_SOURCES = (
    "direct_conversation",
    "shared_scene",
    "delegated_execution",
    "manual",
    "imported",
)
_ROOM_SESSION_SOURCES = (*_LEGACY_SESSION_SOURCES, "companion_home")
_LEGACY_JOIN_STATUSES = ("invited", "active", "paused", "left", "removed")
_ROOM_JOIN_STATUSES = (*_LEGACY_JOIN_STATUSES, "inactive", "revoked")


def _allowed(column: str, values: tuple[str, ...]) -> str:
    joined = ", ".join(repr(value) for value in values)
    return f"{column} IN ({joined})"


def upgrade() -> None:
    op.drop_constraint("ck_cps_source", "co_presence_sessions", type_="check")
    op.create_check_constraint(
        "ck_cps_source",
        "co_presence_sessions",
        _allowed("session_source", _ROOM_SESSION_SOURCES),
    )
    op.drop_constraint("ck_copp_join", "co_presence_participants", type_="check")
    op.create_check_constraint(
        "ck_copp_join",
        "co_presence_participants",
        _allowed("join_status", _ROOM_JOIN_STATUSES),
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE co_presence_participants "
            "SET join_status = CASE WHEN join_status = 'inactive' THEN 'paused' ELSE 'removed' END "
            "WHERE join_status IN ('inactive', 'revoked')"
        )
    )
    op.execute(
        sa.text(
            "UPDATE co_presence_sessions SET session_source = 'manual' "
            "WHERE session_source = 'companion_home'"
        )
    )
    op.drop_constraint("ck_copp_join", "co_presence_participants", type_="check")
    op.create_check_constraint(
        "ck_copp_join",
        "co_presence_participants",
        _allowed("join_status", _LEGACY_JOIN_STATUSES),
    )
    op.drop_constraint("ck_cps_source", "co_presence_sessions", type_="check")
    op.create_check_constraint(
        "ck_cps_source",
        "co_presence_sessions",
        _allowed("session_source", _LEGACY_SESSION_SOURCES),
    )
