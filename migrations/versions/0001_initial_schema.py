"""0001_initial_schema

Revision ID: 0001
Revises: 
Create Date: 2026-10-03 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Sources table
    op.create_table(
        'sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('url', sa.String(length=1024), nullable=False),
        sa.Column('feed_url', sa.String(length=1024), nullable=False),
        sa.Column('source_type', sa.Enum('RSS', 'ATOM', 'JSON_FEED', 'CUSTOM', name='sourcetype'), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=False),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('country', sa.String(length=10), nullable=False),
        sa.Column('trust_level', sa.Enum('LOW', 'MEDIUM', 'HIGH', 'VERIFIED', name='trustlevel'), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False),
        sa.Column('last_fetched_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sources_id'), 'sources', ['id'], unique=False)
    op.create_index(op.f('ix_sources_feed_url'), 'sources', ['feed_url'], unique=True)
    op.create_index(op.f('ix_sources_category'), 'sources', ['category'], unique=False)

    # 2. Articles table
    op.create_table(
        'articles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=512), nullable=False),
        sa.Column('url', sa.String(length=1024), nullable=False),
        sa.Column('canonical_url', sa.String(length=1024), nullable=False),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('published_at', sa.DateTime(), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('image_url', sa.String(length=1024), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('language', sa.String(length=10), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('simhash', sa.String(length=64), nullable=True),
        sa.Column('guid', sa.String(length=512), nullable=True),
        sa.Column('is_duplicate', sa.Boolean(), nullable=False),
        sa.Column('duplicate_of_id', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['duplicate_of_id'], ['articles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_articles_id'), 'articles', ['id'], unique=False)
    op.create_index(op.f('ix_articles_source_id'), 'articles', ['source_id'], unique=False)
    op.create_index(op.f('ix_articles_title'), 'articles', ['title'], unique=False)
    op.create_index(op.f('ix_articles_canonical_url'), 'articles', ['canonical_url'], unique=False)
    op.create_index(op.f('ix_articles_published_at'), 'articles', ['published_at'], unique=False)
    op.create_index(op.f('ix_articles_category'), 'articles', ['category'], unique=False)
    op.create_index(op.f('ix_articles_content_hash'), 'articles', ['content_hash'], unique=True)
    op.create_index(op.f('ix_articles_is_duplicate'), 'articles', ['is_duplicate'], unique=False)

    # 3. Ingestion runs table
    op.create_table(
        'ingestion_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', name='ingestionstatus'), nullable=False),
        sa.Column('articles_found', sa.Integer(), nullable=False),
        sa.Column('articles_ingested', sa.Integer(), nullable=False),
        sa.Column('articles_skipped', sa.Integer(), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['source_id'], ['sources.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_ingestion_runs_id'), 'ingestion_runs', ['id'], unique=False)
    op.create_index(op.f('ix_ingestion_runs_source_id'), 'ingestion_runs', ['source_id'], unique=False)


def downgrade() -> None:
    op.drop_table('ingestion_runs')
    op.drop_table('articles')
    op.drop_table('sources')
