"""0003_editorial_desk

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-04 12:00:00.000000

Phase 3: AI Editorial Desk tables (drafts, generation history, source provenance).
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0003'
down_revision: Union[str, None] = '0002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. editorial_generations (created first; drafts reference it)
    op.create_table(
        'editorial_generations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('story_cluster_id', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=64), nullable=False),
        sa.Column('model', sa.String(length=128), nullable=False),
        sa.Column('prompt_version', sa.String(length=64), nullable=False),
        sa.Column('generation_type', sa.String(length=32), nullable=False),
        sa.Column('input_context_hash', sa.String(length=64), nullable=False),
        sa.Column('output_hash', sa.String(length=64), nullable=True),
        sa.Column('raw_response', sa.Text(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('success', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('error_code', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['story_cluster_id'], ['story_clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_editorial_generations_id'), 'editorial_generations', ['id'], unique=False)
    op.create_index(op.f('ix_editorial_generations_story_cluster_id'), 'editorial_generations', ['story_cluster_id'], unique=False)
    op.create_index(op.f('ix_editorial_generations_generation_type'), 'editorial_generations', ['generation_type'], unique=False)
    op.create_index(op.f('ix_editorial_generations_input_context_hash'), 'editorial_generations', ['input_context_hash'], unique=False)
    op.create_index(op.f('ix_editorial_generations_created_at'), 'editorial_generations', ['created_at'], unique=False)

    # 2. editorial_drafts
    op.create_table(
        'editorial_drafts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('story_cluster_id', sa.Integer(), nullable=False),
        sa.Column('draft_type', sa.String(length=32), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='GENERATED'),
        sa.Column('title', sa.String(length=512), nullable=True),
        sa.Column('body', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('dek', sa.Text(), nullable=True),
        sa.Column('editorial_angle', sa.String(length=128), nullable=True),
        sa.Column('tone', sa.String(length=64), nullable=True),
        sa.Column('target_platform', sa.String(length=64), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=False, server_default='en'),
        sa.Column('payload_json', sa.Text(), nullable=True),
        sa.Column('quality_score', sa.Integer(), nullable=True),
        sa.Column('confidence_score', sa.Integer(), nullable=True),
        sa.Column('quality_breakdown_json', sa.Text(), nullable=True),
        sa.Column('risk_flags_json', sa.Text(), nullable=True),
        sa.Column('generation_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('generated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['generation_id'], ['editorial_generations.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['story_cluster_id'], ['story_clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_editorial_drafts_id'), 'editorial_drafts', ['id'], unique=False)
    op.create_index(op.f('ix_editorial_drafts_story_cluster_id'), 'editorial_drafts', ['story_cluster_id'], unique=False)
    op.create_index(op.f('ix_editorial_drafts_draft_type'), 'editorial_drafts', ['draft_type'], unique=False)
    op.create_index(op.f('ix_editorial_drafts_status'), 'editorial_drafts', ['status'], unique=False)
    op.create_index(op.f('ix_editorial_drafts_generation_id'), 'editorial_drafts', ['generation_id'], unique=False)

    # 3. editorial_draft_sources (provenance)
    op.create_table(
        'editorial_draft_sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('draft_id', sa.Integer(), nullable=False),
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('relevance', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('citation_role', sa.String(length=64), nullable=False, server_default='evidence'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['draft_id'], ['editorial_drafts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('draft_id', 'article_id', name='uq_editorial_draft_sources_draft_article'),
    )
    op.create_index(op.f('ix_editorial_draft_sources_id'), 'editorial_draft_sources', ['id'], unique=False)
    op.create_index(op.f('ix_editorial_draft_sources_draft_id'), 'editorial_draft_sources', ['draft_id'], unique=False)
    op.create_index(op.f('ix_editorial_draft_sources_article_id'), 'editorial_draft_sources', ['article_id'], unique=False)
    op.create_index(op.f('ix_editorial_draft_sources_source_id'), 'editorial_draft_sources', ['source_id'], unique=False)


def downgrade() -> None:
    op.drop_table('editorial_draft_sources')
    op.drop_table('editorial_drafts')
    op.drop_table('editorial_generations')
