"""0002_intelligence_schema

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-03 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. story_clusters
    op.create_table(
        'story_clusters',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('canonical_title', sa.String(length=512), nullable=False),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='EMERGING'),
        sa.Column('first_seen_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
        sa.Column('article_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('source_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('velocity_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('freshness_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('relevance_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('corroboration_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('trending_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('scoring_metadata', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_story_clusters_id'), 'story_clusters', ['id'], unique=False)
    op.create_index(op.f('ix_story_clusters_canonical_title'), 'story_clusters', ['canonical_title'], unique=False)
    op.create_index(op.f('ix_story_clusters_category'), 'story_clusters', ['category'], unique=False)
    op.create_index(op.f('ix_story_clusters_status'), 'story_clusters', ['status'], unique=False)
    op.create_index(op.f('ix_story_clusters_trending_score'), 'story_clusters', ['trending_score'], unique=False)
    op.create_index(op.f('ix_story_clusters_first_seen_at'), 'story_clusters', ['first_seen_at'], unique=False)
    op.create_index(op.f('ix_story_clusters_last_seen_at'), 'story_clusters', ['last_seen_at'], unique=False)

    # 2. entities
    op.create_table(
        'entities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('normalized_name', sa.String(length=256), nullable=False),
        sa.Column('entity_type', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_entities_id'), 'entities', ['id'], unique=False)
    op.create_index(op.f('ix_entities_normalized_name'), 'entities', ['normalized_name'], unique=True)
    op.create_index(op.f('ix_entities_entity_type'), 'entities', ['entity_type'], unique=False)

    # 3. story_cluster_articles
    op.create_table(
        'story_cluster_articles',
        sa.Column('story_cluster_id', sa.Integer(), nullable=False),
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('similarity_score', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('assignment_method', sa.String(length=32), nullable=False, server_default='lexical'),
        sa.Column('assigned_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['story_cluster_id'], ['story_clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('story_cluster_id', 'article_id'),
    )

    # 4. article_entities
    op.create_table(
        'article_entities',
        sa.Column('article_id', sa.Integer(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('extraction_method', sa.String(length=64), nullable=False, server_default='deterministic_nlp'),
        sa.ForeignKeyConstraint(['article_id'], ['articles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('article_id', 'entity_id'),
    )

    # 5. story_cluster_entities
    op.create_table(
        'story_cluster_entities',
        sa.Column('story_cluster_id', sa.Integer(), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=False),
        sa.Column('mention_count', sa.Integer(), nullable=False, server_default='1'),
        sa.ForeignKeyConstraint(['entity_id'], ['entities.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['story_cluster_id'], ['story_clusters.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('story_cluster_id', 'entity_id'),
    )


def downgrade() -> None:
    op.drop_table('story_cluster_entities')
    op.drop_table('article_entities')
    op.drop_table('story_cluster_articles')
    op.drop_table('entities')
    op.drop_table('story_clusters')
