"""add verdicts.validation_status downgraded_reliability_mismatch value

Revision ID: 403a421884b7
Revises: ad9d67b949f7
Create Date: 2026-08-18 04:46:54.942298

"""
from typing import Sequence, Union

from alembic import op

revision: str = '403a421884b7'
down_revision: Union[str, None] = 'ad9d67b949f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE validation_status ADD VALUE IF NOT EXISTS 'downgraded_reliability_mismatch'")


def downgrade() -> None:
    # Postgres cannot drop a single enum value in place. Left as a no-op
    # (additive, backwards-compatible change), same convention as
    # 05807d659a5d_add_verdicts_validation_status_.py.
    pass
