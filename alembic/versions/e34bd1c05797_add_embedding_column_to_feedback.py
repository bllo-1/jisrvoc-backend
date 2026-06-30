"""Add embedding column to feedback

Revision ID: e34bd1c05797
Revises: 8e9788757482
Create Date: 2026-06-29 16:15:36.508026

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = 'e34bd1c05797'
down_revision: Union[str, None] = '8e9788757482'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add embedding column for semantic search (OpenAI text-embedding-3-small = 1536 dimensions)
    op.add_column('feedback', sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=1536), nullable=True))


def downgrade() -> None:
    # Remove embedding column
    op.drop_column('feedback', 'embedding')
