"""core_alg_05_embedding_1024

Revision ID: core_alg_05_embedding_1024
Revises: core_alg_04_memory_graph
Create Date: 2026-06-25 00:00:00.000000

Move embedding vector columns to 1024 dimensions for doubao-embedding-vision.

Existing 768-dimension vectors cannot be safely cast to vector(1024), so the
migration clears embedding columns. Embeddings should be regenerated after the
provider switch.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "core_alg_05_embedding_1024"
down_revision: Union[str, Sequence[str], None] = "core_alg_04_memory_graph"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


EMBEDDING_TABLES = ("memories", "memory_candidates", "file_chunks")


def _set_embedding_dimension(dimension: int) -> None:
    for table in EMBEDDING_TABLES:
        op.execute(f"UPDATE {table} SET embedding = NULL WHERE embedding IS NOT NULL")
        op.execute(
            f"ALTER TABLE {table} "
            f"ALTER COLUMN embedding TYPE vector({dimension}) "
            f"USING NULL::vector({dimension})"
        )


def upgrade() -> None:
    _set_embedding_dimension(1024)


def downgrade() -> None:
    _set_embedding_dimension(768)
