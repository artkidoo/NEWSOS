"""Pydantic schemas for Phase 2 Story Intelligence and Trending Engine."""

from datetime import datetime

from pydantic import BaseModel


class EntityResponse(BaseModel):
    id: int
    name: str
    normalized_name: str
    entity_type: str
    created_at: datetime

    class Config:
        from_attributes = True


class EntityMentionResponse(BaseModel):
    id: int
    name: str
    normalized_name: str
    entity_type: str
    mention_count: int


class StoryArticleItem(BaseModel):
    id: int
    title: str
    url: str
    canonical_url: str
    published_at: datetime
    source_name: str
    source_trust: str
    similarity_score: float
    assignment_method: str


class StoryClusterResponse(BaseModel):
    id: int
    canonical_title: str
    summary: str | None = None
    category: str
    status: str
    first_seen_at: datetime
    last_seen_at: datetime
    article_count: int
    source_count: int
    velocity_score: float
    freshness_score: float
    relevance_score: float
    corroboration_score: float
    trending_score: float
    corroboration_label: str
    scoring_metadata: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class StoryClusterDetailResponse(StoryClusterResponse):
    articles: list[StoryArticleItem] = []
    entities: list[EntityMentionResponse] = []


class ProcessIntelligenceResponse(BaseModel):
    status: str
    articles_evaluated: int
    clusters_created: int
    clusters_updated: int
    entities_extracted: int
    clusters_scored: int
