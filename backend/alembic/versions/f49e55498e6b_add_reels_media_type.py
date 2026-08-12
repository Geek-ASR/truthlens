"""add reels.media_type

Revision ID: f49e55498e6b
Revises: 0245cd2cf1ba
Create Date: 2026-08-12 18:37:15.966466

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f49e55498e6b'
down_revision: Union[str, None] = '0245cd2cf1ba'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Unlike an enum VALUE added to an existing type, a brand-new
    # Postgres ENUM type used in add_column() isn't auto-created --
    # must CREATE TYPE explicitly first.
    media_type_enum = sa.Enum('video', 'photo', name='media_type')
    media_type_enum.create(op.get_bind(), checkfirst=True)
    # server_default so existing rows (all pre-dating photo support, and
    # therefore all videos) backfill correctly instead of failing the
    # NOT NULL constraint on add.
    op.add_column(
        'reels',
        sa.Column('media_type', media_type_enum, nullable=False, server_default='video'),
    )


def downgrade() -> None:
    op.drop_column('reels', 'media_type')
    op.execute('DROP TYPE IF EXISTS media_type')
