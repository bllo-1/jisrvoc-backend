"""add_chargebee_enrichment_fields

Revision ID: 656be9697c79
Revises: dfb1da0fcad9
Create Date: 2026-06-30 15:06:20.785755

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '656be9697c79'
down_revision: Union[str, None] = 'dfb1da0fcad9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add Chargebee enrichment fields to feedback_item table
    op.add_column('feedback_item', sa.Column('customer_mrr', sa.Numeric(10, 2), nullable=True))
    op.add_column('feedback_item', sa.Column('customer_ltv', sa.Numeric(10, 2), nullable=True))
    op.add_column('feedback_item', sa.Column('churn_risk_score', sa.Integer(), nullable=True))
    op.add_column('feedback_item', sa.Column('subscription_plan', sa.String(100), nullable=True))
    op.add_column('feedback_item', sa.Column('enriched_at', sa.DateTime(timezone=True), nullable=True))

    # Add index for filtering by customer segment (already exists, but ensure it's there)
    # Note: This index might already exist from previous migrations, so we wrap in try/catch
    try:
        op.create_index('idx_feedback_customer_segment', 'feedback_item', ['segment'], unique=False)
    except:
        pass  # Index already exists

    # Add index for churn risk filtering
    op.create_index('idx_feedback_churn_risk', 'feedback_item', ['churn_risk_score'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_feedback_churn_risk', table_name='feedback_item')
    # Don't drop idx_feedback_customer_segment as it might be used elsewhere

    # Drop columns
    op.drop_column('feedback_item', 'enriched_at')
    op.drop_column('feedback_item', 'subscription_plan')
    op.drop_column('feedback_item', 'churn_risk_score')
    op.drop_column('feedback_item', 'customer_ltv')
    op.drop_column('feedback_item', 'customer_mrr')
