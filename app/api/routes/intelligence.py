"""Intelligence and Trending API Routes."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.article import Article
from app.models.intelligence import (
    Entity,
    StoryCluster,
    StoryClusterArticle,
    StoryClusterEntity,
)
from app.models.source import Source
from app.schemas.intelligence import (
    EntityMentionResponse,
    EntityResponse,
    ProcessIntelligenceResponse,
    StoryArticleItem,
    StoryClusterDetailResponse,
    StoryClusterResponse,
)
from app.services.intelligence.pipeline import IntelligencePipeline

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


def format_cluster_response(cluster: StoryCluster, db: Session) -> StoryClusterResponse:
    """Helper to assemble explainable StoryClusterResponse with corroboration label."""
    label = f"Reported by {cluster.source_count} independent {'source' if cluster.source_count == 1 else 'sources'}"
    if cluster.scoring_metadata:
        try:
            meta = json.loads(cluster.scoring_metadata)
            label = meta.get("corroboration_label", label)
        except Exception:
            pass

    return StoryClusterResponse(
        id=cluster.id,
        canonical_title=cluster.canonical_title,
        summary=cluster.summary,
        category=cluster.category,
        status=cluster.status,
        first_seen_at=cluster.first_seen_at,
        last_seen_at=cluster.last_seen_at,
        article_count=cluster.article_count,
        source_count=cluster.source_count,
        velocity_score=cluster.velocity_score,
        freshness_score=cluster.freshness_score,
        relevance_score=cluster.relevance_score,
        corroboration_score=cluster.corroboration_score,
        trending_score=cluster.trending_score,
        corroboration_label=label,
        scoring_metadata=cluster.scoring_metadata,
        created_at=cluster.created_at,
        updated_at=cluster.updated_at,
    )


@router.get("/stories", response_model=list[StoryClusterResponse])
def list_stories(
    category: str | None = None,
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Lists all story clusters ordered by recency."""
    query = db.query(StoryCluster)
    if category:
        query = query.filter(StoryCluster.category == category)
    if status_filter:
        query = query.filter(StoryCluster.status == status_filter)
    clusters = query.order_by(StoryCluster.last_seen_at.desc()).offset(skip).limit(limit).all()
    return [format_cluster_response(c, db) for c in clusters]


@router.get("/trending", response_model=list[StoryClusterResponse])
def list_trending(
    limit: int = Query(20, ge=1, le=100),
    category: str | None = None,
    db: Session = Depends(get_db),
):
    """Returns top ranked trending stories by composite trending score."""
    query = db.query(StoryCluster)
    if category:
        query = query.filter(StoryCluster.category == category)
    clusters = query.order_by(StoryCluster.trending_score.desc()).limit(limit).all()
    return [format_cluster_response(c, db) for c in clusters]


@router.get("/stories/{story_id}", response_model=StoryClusterDetailResponse)
def get_story_detail(story_id: int, db: Session = Depends(get_db)):
    """Returns granular story cluster breakdown including constituent articles and extracted entities."""
    cluster = db.query(StoryCluster).filter(StoryCluster.id == story_id).first()
    if not cluster:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story cluster not found.")

    base_resp = format_cluster_response(cluster, db)

    # Fetch articles
    article_links = (
        db.query(StoryClusterArticle, Article, Source)
        .join(Article, Article.id == StoryClusterArticle.article_id)
        .join(Source, Source.id == Article.source_id)
        .filter(StoryClusterArticle.story_cluster_id == story_id)
        .order_by(Article.published_at.desc())
        .all()
    )

    articles_list = [
        StoryArticleItem(
            id=art.id,
            title=art.title,
            url=art.url,
            canonical_url=art.canonical_url,
            published_at=art.published_at,
            source_name=src.name,
            source_trust=src.trust_level.value,
            similarity_score=link.similarity_score,
            assignment_method=link.assignment_method,
        )
        for link, art, src in article_links
    ]

    # Fetch entities
    entity_links = (
        db.query(StoryClusterEntity, Entity)
        .join(Entity, Entity.id == StoryClusterEntity.entity_id)
        .filter(StoryClusterEntity.story_cluster_id == story_id)
        .order_by(StoryClusterEntity.mention_count.desc())
        .all()
    )

    entities_list = [
        EntityMentionResponse(
            id=ent.id,
            name=ent.name,
            normalized_name=ent.normalized_name,
            entity_type=ent.entity_type,
            mention_count=link.mention_count,
        )
        for link, ent in entity_links
    ]

    return StoryClusterDetailResponse(
        **base_resp.model_dump(),
        articles=articles_list,
        entities=entities_list,
    )


@router.get("/entities", response_model=list[EntityResponse])
def list_entities(
    entity_type: str | None = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Lists extracted named entities."""
    query = db.query(Entity)
    if entity_type:
        query = query.filter(Entity.entity_type == entity_type)
    return query.order_by(Entity.name.asc()).offset(skip).limit(limit).all()


@router.post("/process", response_model=ProcessIntelligenceResponse)
@router.get("/process", response_model=ProcessIntelligenceResponse)
def process_intelligence(limit: int = Query(200, ge=1, le=500), db: Session = Depends(get_db)):
    """Triggers the end-to-end intelligence pipeline on unassigned and recent articles."""
    pipeline = IntelligencePipeline(db)
    result = pipeline.run_pipeline(limit=limit)
    return ProcessIntelligenceResponse(
        status="success",
        **result,
    )


@router.post("/rebuild", response_model=ProcessIntelligenceResponse)
@router.get("/rebuild", response_model=ProcessIntelligenceResponse)
def rebuild_clusters(db: Session = Depends(get_db)):
    """Rebuilds clusters from scratch and rescores all stories."""
    # Delete cluster associations and clusters
    db.query(StoryClusterArticle).delete()
    db.query(StoryClusterEntity).delete()
    db.query(StoryCluster).delete()
    db.commit()

    pipeline = IntelligencePipeline(db)
    result = pipeline.run_pipeline(limit=500)
    return ProcessIntelligenceResponse(
        status="rebuilt",
        **result,
    )
