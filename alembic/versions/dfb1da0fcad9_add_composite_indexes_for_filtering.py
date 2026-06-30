"""add_composite_indexes_for_filtering

Revision ID: dfb1da0fcad9
Revises: bd5d2cb7d69c
Create Date: 2026-06-30 10:07:51.527137

Add composite indexes for common filter combinations to optimize
feed queries with multiple dimensions.

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dfb1da0fcad9'
down_revision: Union[str, None] = 'bd5d2cb7d69c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add composite indexes for common filter combinations."""

    # Composite index for occurred_at + area (common filter: recent feedback in an area)
    op.create_index(
        'idx_fi_occurred_area',
        'feedback_item',
        ['occurred_at', 'area'],
        postgresql_ops={'occurred_at': 'DESC'}
    )

    # Composite index for area + urgency (common filter: high urgency items per area)
    op.create_index(
        'idx_fi_area_urgency',
        'feedback_item',
        ['area', 'urgency']
    )

    # Composite index for occurred_at + urgency (common filter: recent high urgency)
    op.create_index(
        'idx_fi_occurred_urgency',
        'feedback_item',
        ['occurred_at', 'urgency'],
        postgresql_ops={'occurred_at': 'DESC'}
    )

    # Composite index for segment + area (common filter: segment-specific area feedback)
    op.create_index(
        'idx_fi_segment_area',
        'feedback_item',
        ['segment', 'area']
    )


def downgrade() -> None:
    """Remove composite indexes."""

    op.drop_index('idx_fi_segment_area', table_name='feedback_item')
    op.drop_index('idx_fi_occurred_urgency', table_name='feedback_item')
    op.drop_index('idx_fi_area_urgency', table_name='feedback_item')
    op.drop_index('idx_fi_occurred_area', table_name='feedback_item')
