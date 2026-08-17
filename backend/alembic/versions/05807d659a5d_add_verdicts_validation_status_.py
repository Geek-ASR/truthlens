"""add verdicts.validation_status downgraded_entity_mismatch value

Revision ID: 05807d659a5d
Revises: d051214c1b0d
Create Date: 2026-08-18 00:18:49.388264

"""
from typing import Sequence, Union

from alembic import op

revision: str = '05807d659a5d'
down_revision: Union[str, None] = 'd051214c1b0d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE validation_status ADD VALUE IF NOT EXISTS 'downgraded_entity_mismatch'")


def downgrade() -> None:
    # Postgres cannot drop a single enum value in place. Left as a no-op
    # (additive, backwards-compatible change), same convention as
    # 55e097a9b286_add_verdicts_validation_status_.py.
    pass
