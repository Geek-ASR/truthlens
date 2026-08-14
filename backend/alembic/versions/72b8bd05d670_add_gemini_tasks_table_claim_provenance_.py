"""add gemini_tasks table, claim provenance fields, reel dataset scoping

Revision ID: 72b8bd05d670
Revises: 55e097a9b286
Create Date: 2026-08-14 21:14:55.768854

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = '72b8bd05d670'
down_revision: Union[str, None] = '55e097a9b286'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New table's own enum columns are created implicitly by create_table.
    op.create_table('gemini_tasks',
    sa.Column('item_id', sa.String(length=255), nullable=True),
    sa.Column('stage', sa.String(length=64), nullable=False),
    sa.Column('input_hash', sa.String(length=64), nullable=False),
    sa.Column('prompt_version', sa.String(length=64), nullable=False),
    sa.Column('model', sa.String(length=128), nullable=False),
    sa.Column('status', sa.Enum('pending', 'running', 'completed', 'failed', 'quota_wait', 'permanent_failure', name='gemini_task_status'), nullable=False),
    sa.Column('attempt_count', sa.Integer(), nullable=False),
    sa.Column('last_error', sa.Text(), nullable=True),
    sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('result_json', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_gemini_tasks_input_hash'), 'gemini_tasks', ['input_hash'], unique=False)
    op.create_index(op.f('ix_gemini_tasks_item_id'), 'gemini_tasks', ['item_id'], unique=False)
    op.create_index(op.f('ix_gemini_tasks_stage'), 'gemini_tasks', ['stage'], unique=False)
    op.create_index(op.f('ix_gemini_tasks_status'), 'gemini_tasks', ['status'], unique=False)

    op.add_column('claims', sa.Column('source_modalities', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.add_column('claims', sa.Column('extraction_confidence', sa.Float(), nullable=True))
    op.add_column('claims', sa.Column('confidence_type', sa.String(length=32), nullable=True))
    # Existing enum type added via add_column() to an existing table
    # needs an explicit CREATE TYPE first (unlike create_table, which
    # handles it implicitly) -- same pattern as
    # f49e55498e6b_add_reels_media_type.py.
    claim_verifiability_enum = sa.Enum('verifiable', 'not_verifiable', 'uncertain', name='claim_verifiability')
    claim_verifiability_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('claims', sa.Column('verifiability', claim_verifiability_enum, nullable=True))
    op.add_column('claims', sa.Column('provenance_detail', postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    dataset_type_enum = sa.Enum('development', 'benchmark', 'regression', 'synthetic', name='dataset_type')
    dataset_type_enum.create(op.get_bind(), checkfirst=True)
    # server_default so all 20 existing reels (predating this migration,
    # therefore all real dev/manual-testing records, never a benchmark
    # item collected under the new scoping discipline) backfill to
    # 'development' rather than failing the NOT NULL constraint.
    op.add_column('reels', sa.Column('dataset_type', dataset_type_enum, nullable=False, server_default='development'))
    op.add_column('reels', sa.Column('benchmark_version', sa.String(length=32), nullable=True))
    benchmark_split_enum = sa.Enum('dev', 'validation', 'test', name='benchmark_split')
    benchmark_split_enum.create(op.get_bind(), checkfirst=True)
    op.add_column('reels', sa.Column('benchmark_split', benchmark_split_enum, nullable=True))


def downgrade() -> None:
    op.drop_column('reels', 'benchmark_split')
    op.execute('DROP TYPE IF EXISTS benchmark_split')
    op.drop_column('reels', 'benchmark_version')
    op.drop_column('reels', 'dataset_type')
    op.execute('DROP TYPE IF EXISTS dataset_type')
    op.drop_column('claims', 'provenance_detail')
    op.drop_column('claims', 'verifiability')
    op.execute('DROP TYPE IF EXISTS claim_verifiability')
    op.drop_column('claims', 'confidence_type')
    op.drop_column('claims', 'extraction_confidence')
    op.drop_column('claims', 'source_modalities')
    op.drop_index(op.f('ix_gemini_tasks_status'), table_name='gemini_tasks')
    op.drop_index(op.f('ix_gemini_tasks_stage'), table_name='gemini_tasks')
    op.drop_index(op.f('ix_gemini_tasks_item_id'), table_name='gemini_tasks')
    op.drop_index(op.f('ix_gemini_tasks_input_hash'), table_name='gemini_tasks')
    op.drop_table('gemini_tasks')
    op.execute('DROP TYPE IF EXISTS gemini_task_status')
