"""R1-B1 Companion product-scope governance.

Revision ID: r1_b1_companion_governance
Revises: core_alg_05_embedding_1024
Create Date: 2026-07-14 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "r1_b1_companion_governance"
down_revision: Union[str, Sequence[str], None] = "core_alg_05_embedding_1024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ENVIRONMENTS = ("unclassified", "product", "test")
PROVENANCE = ("legacy", "user_created", "seed", "smoke", "import", "system")
OLD_LIFECYCLE_EVENTS = (
    "default_companion_upgraded",
    "companion_profile_backfilled",
    "identity_profile_initialized",
    "persona_profile_initialized",
    "relationship_contract_initialized",
    "boundary_profile_initialized",
    "visibility_policy_initialized",
)
NEW_LIFECYCLE_EVENTS = OLD_LIFECYCLE_EVENTS + (
    "classification_changed",
    "classification_reverted",
)


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(value) for value in values)})"


def upgrade() -> None:
    op.add_column("companions", sa.Column("companion_environment", sa.Text(), nullable=True))
    op.add_column("companions", sa.Column("provenance", sa.Text(), nullable=True))
    op.execute("UPDATE companions SET companion_environment='unclassified', provenance='legacy'")
    op.alter_column("companions", "companion_environment", nullable=False, server_default=sa.text("'product'"))
    op.alter_column("companions", "provenance", nullable=False, server_default=sa.text("'user_created'"))
    op.create_check_constraint("ck_companions_environment", "companions", _in("companion_environment", ENVIRONMENTS))
    op.create_check_constraint("ck_companions_provenance", "companions", _in("provenance", PROVENANCE))
    op.create_index(
        "idx_companions_user_environment",
        "companions",
        ["user_id", "companion_environment", "deleted_at"],
    )

    op.drop_constraint("ck_cle_event_type", "companion_lifecycle_events", type_="check")
    op.create_check_constraint(
        "ck_cle_event_type",
        "companion_lifecycle_events",
        _in("event_type", NEW_LIFECYCLE_EVENTS),
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM companion_lifecycle_events changed
                WHERE changed.event_type = 'classification_changed'
                  AND NOT EXISTS (
                      SELECT 1
                      FROM companion_lifecycle_events reverted
                      WHERE reverted.event_type = 'classification_reverted'
                        AND reverted.metadata->>'reverts_batch_id' =
                            changed.metadata->>'classification_batch_id'
                  )
            ) THEN
                RAISE EXCEPTION
                    'R1-B1 downgrade refused: roll back every applied classification batch first.';
            END IF;
        END $$
        """
    )
    # Keep classification event types and rows as durable audit evidence.
    op.drop_index("idx_companions_user_environment", table_name="companions")
    op.drop_constraint("ck_companions_provenance", "companions", type_="check")
    op.drop_constraint("ck_companions_environment", "companions", type_="check")
    op.drop_column("companions", "provenance")
    op.drop_column("companions", "companion_environment")
