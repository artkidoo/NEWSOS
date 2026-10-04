# NEWSROOM OS — System Architecture

## Architecture Diagram
```
[Syndicated Feeds (RSS/Atom)]
            │
            ▼
[Discovery & FeedClient] ──► [FeedDetector]
            │
            ▼
[ArticleNormalizer] ──► Canonical URL, Content Hash (SHA-256)
            │
            ▼
[Deduplicator] ───────► Filters Exact & Near Duplicates (Threshold >= 0.85)
            │
            ▼
     [Database Articles]
            │
            ▼
[IntelligencePipeline]
 ├── [EntityExtractor] ──────────► (Entities & ArticleEntities)
 ├── [ClusteringEngine] ─────────► Bounded 48h Candidate Search
 ├── [VelocityEngine] ───────────► 6h/12h Window Acceleration
 ├── [FreshnessEngine] ──────────► Exponential Decay (12h Half-life)
 ├── [CorroborationEngine] ──────► Distinct Source Trust Weighting
 ├── [RelevanceEngine] ──────────► Category & Entity Density
 └── [TrendingEngine] ───────────► Composite Score & Story State Machine
            │
            ▼
     [StoryClusters]
            │
            ▼
    [FastAPI REST API] ──────────► [React 19 Vite Dashboard]
```

## Database Schema (Alembic 0001 + 0002)
1. `sources`: Feed configurations, URLs, categories, trust levels (`LOW`, `MEDIUM`, `HIGH`, `VERIFIED`).
2. `articles`: Canonicalized articles, SHA-256 content hashes, deduplication pointers.
3. `ingestion_runs`: Execution audit trail with counts of found, ingested, and skipped items.
4. `story_clusters`: Clustered events, velocity, freshness, corroboration, relevance, and trending score.
5. `story_cluster_articles`: M:N link between articles and clusters with similarity scores.
6. `entities`: Normalized named entities (`normalized_name` unique index).
7. `article_entities`: Confidence-weighted entity extraction links.
8. `story_cluster_entities`: Entity mention frequency across stories.
