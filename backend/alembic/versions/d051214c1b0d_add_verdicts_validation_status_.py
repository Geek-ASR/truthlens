"""add verdicts.validation_status downgraded_temporal_mismatch value

Revision ID: d051214c1b0d
Revises: 72b8bd05d670
Create Date: 2026-08-18 00:08:02.987737

"""
from typing import Sequence, Union

from alembic import op

revision: str = 'd051214c1b0d'
down_revision: Union[str, None] = '72b8bd05d670'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE validation_status ADD VALUE IF NOT EXISTS 'downgraded_temporal_mismatch'")


def downgrade() -> None:
    # Postgres cannot drop a single enum value in place. Left as a no-op
    # (additive, backwards-compatible change), same convention as
    # 55e097a9b286_add_verdicts_validation_status_.py.
    pass
