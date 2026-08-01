"""add_committed_status_to_memory_candidates

Revision ID: 9d0fd148cb7b
Revises: 908db3efc215
Create Date: 2026-05-28 14:08:57.011393

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d0fd148cb7b'
down_revision: Union[str, Sequence[str], None] = '908db3efc215'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add 'committed' to memory_candidates.status CHECK constraint."""
    # Drop old constraint
    op.execute(
        "ALTER TABLE memory_candidates DROP CONSTRAINT IF EXISTS ck_memory_candidates_status"
    )
    # Re-add with 'committed' included
    op.execute(
        "ALTER TABLE memory_candidates ADD CONSTRAINT ck_memory_candidates_status "
        "CHECK (status IN ('pending', 'accepted', 'edited', 'rejected', 'merged', 'expired', 'committed'))"
    )


def downgrade() -> None:
    """Revert to original CHECK without 'committed'."""
    op.execute(
        "ALTER TABLE memory_candidates DROP CONSTRAINT IF EXISTS ck_memory_candidates_status"
    )
    op.execute(
        "ALTER TABLE memory_candidates ADD CONSTRAINT ck_memory_candidates_status "
        "CHECK (status IN ('pending', 'accepted', 'edited', 'rejected', 'merged', 'expired'))"
    )
