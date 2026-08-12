"""add fact_checks.overall_verdict_label/reasoning

Revision ID: 0245cd2cf1ba
Revises: 2159f6a269bf
Create Date: 2026-08-12 03:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = '0245cd2cf1ba'
down_revision: Union[str, None] = '2159f6a269bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('fact_checks', sa.Column('overall_verdict_label', sa.String(length=32), nullable=True))
    op.add_column('fact_checks', sa.Column('overall_verdict_reasoning', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('fact_checks', 'overall_verdict_reasoning')
    op.drop_column('fact_checks', 'overall_verdict_label')
