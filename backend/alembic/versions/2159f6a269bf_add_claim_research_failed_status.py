"""add claims.status research_failed value

Revision ID: 2159f6a269bf
Revises: 461f46ab44cd
Create Date: 2026-08-12 02:30:00.000000

"""
from typing import Sequence, Union

from alembic import op

revision: str = '2159f6a269bf'
down_revision: Union[str, None] = '461f46ab44cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE claim_status ADD VALUE IF NOT EXISTS 'research_failed'")


def downgrade() -> None:
    # Postgres cannot drop a single enum value in place. Downgrading this
    # migration would require rebuilding the claim_status type without it;
    # left as a no-op since this is an additive, backwards-compatible change
    # (no existing row will ever have this value unless upgrade() ran and
    # the application actually used it).
    pass
