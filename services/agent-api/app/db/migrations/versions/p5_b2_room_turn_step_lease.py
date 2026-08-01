"""Add recoverable leases to P5-B2 Room Turn Steps.

Revision ID: p5_b2_room_turn_step_lease
Revises: p5_b2_room_turn_runtime
"""

from alembic import op
import sqlalchemy as sa


revision = "p5_b2_room_turn_step_lease"
down_revision = "p5_b2_room_turn_runtime"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companion_room_turn_steps", sa.Column("lease_owner", sa.String(length=100), nullable=True))
    op.add_column("companion_room_turn_steps", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_room_turn_step_lease", "companion_room_turn_steps", ["status", "lease_expires_at"])


def downgrade() -> None:
    op.drop_index("ix_room_turn_step_lease", table_name="companion_room_turn_steps")
    op.drop_column("companion_room_turn_steps", "lease_expires_at")
    op.drop_column("companion_room_turn_steps", "lease_owner")
