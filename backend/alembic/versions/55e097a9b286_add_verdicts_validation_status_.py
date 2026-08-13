"""add verdicts.validation_status downgraded_reasoning_label_mismatch value

Revision ID: 55e097a9b286
Revises: d4b85e87ec45
Create Date: 2026-08-13 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = '55e097a9b286'
down_revision: Union[str, None] = 'd4b85e87ec45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE validation_status ADD VALUE IF NOT EXISTS 'downgraded_reasoning_label_mismatch'")


def downgrade() -> None:
    # Postgres cannot drop a single enum value in place. Left as a no-op
    # (additive, backwards-compatible change), same convention as
    # 2159f6a269bf_add_claim_research_failed_status.py.
    pass
