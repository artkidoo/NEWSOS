"""Comprehensive tests for Phase 2 Story Intelligence and Trending Engine."""

import json
from datetime import datetime, timedelta, timezone

from app.models.article import Article
from app.models.enums import TrustLevel
from app.models.intelligence import (
    ArticleEntity,
    Entity,
    StoryCluster,
    StoryClusterArticle,
)
from app.models.source import Source
from app.services.intelligence.clustering.engine import ClusteringEngine
from app.services.intelligence.corroboration.engine import CorroborationEngine
from app.services.intelligence.entities.extractor import EntityExtractor
from app.services.intelligence.freshness.engine import FreshnessEngine
from app.services.intelligence.pipeline import IntelligencePipeline
from app.services.intelligence.relevance.engine import RelevanceEngine
from app.services.intelligence.trending.engine import TrendingEngine
from app.services.intelligence.velocity.engine import VelocityEngine

# ==========================================
# 1. SIMILARITY TESTS
# ==========================================

def test_similarity_identical_titles():
    """Identical titles produce 1.0 similarity."""
    t1 = "Global Climate Accord Reached in Geneva"
    t2 = "Global Climate Accord Reached in Geneva"
    assert ClusteringEngine.calculate_lexical_similarity(t1, t2) == 1.0


def test_similarity_near_identical_titles():
    """Near identical titles produce high similarity (> 0.70)."""
    t1 = "Global Climate Accord Reached in Geneva Today"
    t2 = "Global Climate Accord Reached in Geneva"
    sim = ClusteringEngine.calculate_lexical_similarity(t1, t2)
    assert sim >= 0.70


def test_similarity_partially_overlapping_titles():
    """Partially overlapping titles produce intermediate similarity."""
    t1 = "Global Summit Discusses Trade and Energy"
    t2 = "Global Leaders Gather for Economic Summit"
    sim = ClusteringEngine.calculate_lexical_similarity(t1, t2)
    assert 0.0 < sim < 0.60


def test_similarity_unrelated_titles():
    """Unrelated titles return 0.0 similarity."""
    t1 = "Apple Launches New iPhone 16 With AI Camera"
    t2 = "Earthquake Shakes Northern Japan Coastline"
    assert ClusteringEngine.calculate_lexical_similarity(t1, t2) == 0.0


def test_similarity_threshold_boundary():
    """Threshold boundary discriminates match versus separate."""
    t1 = "Major Earthquake Strikes Pacific Coast Region"
    t2 = "Severe Earthquake Strikes Pacific Coast"
    sim = ClusteringEngine.calculate_lexical_similarity(t1, t2)
    assert sim >= ClusteringEngine.SIMILARITY_THRESHOLD


# ==========================================
# 2. CLUSTERING QUALITY & CANDIDATE SEARCH
# ==========================================

def test_clustering_same_event_high_similarity(db_session, sample_source):
    """Articles on the same event cluster together."""
    now = datetime.now(timezone.utc)
    art1 = Article(
        source_id=sample_source.id,
        title="World Leaders Sign Historic Clean Energy Pact",
        url="https://source-a.example.com/1",
        canonical_url="https://source-a.example.com/1",
        published_at=now,
        content_hash="c_art_1",
        category="world",
    )
    art2 = Article(
        source_id=sample_source.id,
        title="Historic Clean Energy Pact Signed by World Leaders",
        url="https://source-b.example.com/2",
        canonical_url="https://source-b.example.com/2",
        published_at=now + timedelta(minutes=15),
        content_hash="c_art_2",
        category="world",
    )
    db_session.add_all([art1, art2])
    db_session.commit()

    cluster = ClusteringEngine.create_cluster_for_article(db_session, art1)
    best_cluster, score = ClusteringEngine.find_best_cluster(db_session, art2)

    assert best_cluster is not None
    assert best_cluster.id == cluster.id
    assert score >= 0.70


def test_clustering_unrelated_events(db_session, sample_source):
    """Articles on unrelated events do not cluster."""
    now = datetime.now(timezone.utc)
    art1 = Article(
        source_id=sample_source.id,
        title="Central Bank Lowers Benchmark Interest Rates",
        url="https://source-a.example.com/3",
        canonical_url="https://source-a.example.com/3",
        published_at=now,
        content_hash="c_art_3",
        category="business",
    )
    art2 = Article(
        source_id=sample_source.id,
        title="Hurricane Forms in Atlantic Warning Issued",
        url="https://source-b.example.com/4",
        canonical_url="https://source-b.example.com/4",
        published_at=now,
        content_hash="c_art_4",
        category="world",
    )
    db_session.add_all([art1, art2])
    db_session.commit()

    ClusteringEngine.create_cluster_for_article(db_session, art1)
    best_cluster, score = ClusteringEngine.find_best_cluster(db_session, art2)
    assert best_cluster is None
    assert score == 0.0


def test_clustering_anti_spurious_same_person_different_events():
    """Artist X releases album vs Artist X attends football match MUST NOT cluster."""
    t1 = "Burna Boy Releases New Studio Album Across Platforms"
    t2 = "Burna Boy Attends Premier League Football Match in London"
    sim = ClusteringEngine.calculate_lexical_similarity(t1, t2)
    assert sim == 0.0 or sim < ClusteringEngine.SIMILARITY_THRESHOLD


def test_clustering_anti_spurious_same_org_different_events():
    """Apple launches new iPhone vs Apple reports quarterly earnings MUST NOT cluster."""
    t1 = "Apple Launches New iPhone With Advanced Chipset"
    t2 = "Apple Reports Record Quarterly Earnings Driven by Services"
    sim = ClusteringEngine.calculate_lexical_similarity(t1, t2)
    assert sim == 0.0 or sim < ClusteringEngine.SIMILARITY_THRESHOLD


def test_clustering_category_isolation(db_session, sample_source):
    """Articles in different non-general categories do not cluster even with word overlap."""
    now = datetime.now(timezone.utc)
    art1 = Article(
        source_id=sample_source.id,
        title="New Autonomous Electric Vehicle Test Drive",
        url="https://source-a.example.com/5",
        canonical_url="https://source-a.example.com/5",
        published_at=now,
        content_hash="c_art_5",
        category="technology",
    )
    art2 = Article(
        source_id=sample_source.id,
        title="New Autonomous Electric Vehicle Financial Market Stock",
        url="https://source-b.example.com/6",
        canonical_url="https://source-b.example.com/6",
        published_at=now,
        content_hash="c_art_6",
        category="sports",  # Deliberate distinct category
    )
    db_session.add_all([art1, art2])
    db_session.commit()

    ClusteringEngine.create_cluster_for_article(db_session, art1)
    best_cluster, _ = ClusteringEngine.find_best_cluster(db_session, art2)
    assert best_cluster is None


def test_clustering_time_window_boundary(db_session, sample_source):
    """Articles published beyond the candidate window (48h) do not cluster."""
    old_time = datetime.now(timezone.utc) - timedelta(hours=72)
    now = datetime.now(timezone.utc)

    art1 = Article(
        source_id=sample_source.id,
        title="Volcano Eruption Forces Coastal Evacuations",
        url="https://source-a.example.com/7",
        canonical_url="https://source-a.example.com/7",
        published_at=old_time,
        content_hash="c_art_7",
        category="world",
    )
    art2 = Article(
        source_id=sample_source.id,
        title="Volcano Eruption Forces Coastal Evacuations",
        url="https://source-b.example.com/8",
        canonical_url="https://source-b.example.com/8",
        published_at=now,
        content_hash="c_art_8",
        category="world",
    )
    db_session.add_all([art1, art2])
    db_session.commit()

    ClusteringEngine.create_cluster_for_article(db_session, art1)
    best_cluster, _ = ClusteringEngine.find_best_cluster(db_session, art2, window_hours=48)
    assert best_cluster is None


# ==========================================
# 3. ENTITY EXTRACTION TESTS
# ==========================================

def test_entity_extraction_types():
    """Extracts organizations, brands, locations, and proper nouns."""
    title = "Apple and BBC Announce Joint Initiative in London and Nigeria"
    extracted = EntityExtractor.extract_entities(title)
    names = {e[0].lower(): e[1] for e in extracted}

    assert "apple" in names
    assert names["apple"] == "brand"
    assert "bbc" in names
    assert names["bbc"] == "organization"
    assert "london" in names
    assert names["london"] == "location"
    assert "nigeria" in names
    assert names["nigeria"] == "country"


def test_entity_normalization():
    """Entity normalizer cleans special characters into snake_case."""
    norm = EntityExtractor.normalize_name("United Nations / UN (Global)!")
    assert norm == "united_nations_un_global"


def test_entity_idempotent_linking(db_session, sample_source):
    """Repeated extraction does not duplicate entities or links."""
    pipeline = IntelligencePipeline(db_session)
    art = Article(
        source_id=sample_source.id,
        title="Google Launches Gemini in Tokyo",
        url="https://example.com/ent-1",
        canonical_url="https://example.com/ent-1",
        published_at=datetime.now(timezone.utc),
        content_hash="ent_hash_1",
    )
    db_session.add(art)
    db_session.commit()

    ents1 = pipeline.extract_and_link_entities(art)
    ents2 = pipeline.extract_and_link_entities(art)

    assert len(ents1) == len(ents2)
    # Check database entities count
    assert db_session.query(Entity).filter(Entity.normalized_name == "google").count() == 1
    assert db_session.query(ArticleEntity).filter(ArticleEntity.article_id == art.id).count() == len(ents1)


# ==========================================
# 4. CORROBORATION TESTS
# ==========================================

def test_corroboration_single_source(db_session, sample_source):
    """Single source gets baseline corroboration score (~20-30) and proper label."""
    cluster = StoryCluster(
        canonical_title="Uncorroborated Solo Dispatch",
        category="general",
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db_session.add(cluster)
    db_session.commit()

    art = Article(
        source_id=sample_source.id,
        title="Uncorroborated Solo Dispatch",
        url="https://example.com/solo",
        canonical_url="https://example.com/solo",
        published_at=datetime.now(timezone.utc),
        content_hash="solo_hash",
    )
    db_session.add(art)
    db_session.commit()

    link = StoryClusterArticle(story_cluster_id=cluster.id, article_id=art.id)
    db_session.add(link)
    db_session.commit()

    score, label, distinct_count = CorroborationEngine.calculate_corroboration(db_session, cluster)
    assert distinct_count == 1
    assert 20.0 <= score <= 35.0
    assert "Reported by 1 independent source" in label


def test_corroboration_multiple_sources_higher_score(db_session, sample_source):
    """Multiple independent sources increase corroboration score significantly."""
    # Create second source
    src2 = Source(
        name="Independent Tribune",
        url="https://tribune.example.com",
        feed_url="https://tribune.example.com/rss",
        trust_level=TrustLevel.VERIFIED,
    )
    db_session.add(src2)
    db_session.commit()

    cluster = StoryCluster(
        canonical_title="Multi Source Verified Event",
        category="world",
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db_session.add(cluster)
    db_session.commit()

    art1 = Article(
        source_id=sample_source.id,
        title="Multi Source Verified Event",
        url="https://example.com/m1",
        canonical_url="https://example.com/m1",
        published_at=datetime.now(timezone.utc),
        content_hash="m_hash_1",
    )
    art2 = Article(
        source_id=src2.id,
        title="Multi Source Verified Event Coverage",
        url="https://example.com/m2",
        canonical_url="https://example.com/m2",
        published_at=datetime.now(timezone.utc),
        content_hash="m_hash_2",
    )
    db_session.add_all([art1, art2])
    db_session.commit()

    db_session.add_all([
        StoryClusterArticle(story_cluster_id=cluster.id, article_id=art1.id),
        StoryClusterArticle(story_cluster_id=cluster.id, article_id=art2.id),
    ])
    db_session.commit()

    score, label, distinct_count = CorroborationEngine.calculate_corroboration(db_session, cluster)
    assert distinct_count == 2
    assert score >= 60.0
    assert "Reported by 2 independent sources" in label


def test_corroboration_repeated_same_source_not_boosted(db_session, sample_source):
    """5 articles from the exact same source count as 1 source."""
    cluster = StoryCluster(
        canonical_title="Single Publisher Many Articles",
        category="general",
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db_session.add(cluster)
    db_session.commit()

    for i in range(5):
        art = Article(
            source_id=sample_source.id,
            title=f"Article Iteration {i}",
            url=f"https://example.com/iter/{i}",
            canonical_url=f"https://example.com/iter/{i}",
            published_at=datetime.now(timezone.utc),
            content_hash=f"iter_hash_{i}",
        )
        db_session.add(art)
        db_session.commit()
        db_session.add(StoryClusterArticle(story_cluster_id=cluster.id, article_id=art.id))
    db_session.commit()

    score, label, distinct_count = CorroborationEngine.calculate_corroboration(db_session, cluster)
    assert distinct_count == 1
    assert "Reported by 1 independent source" in label


# ==========================================
# 5. VELOCITY & FRESHNESS TESTS
# ==========================================

def test_freshness_decay_curve():
    """Verify exponential half-life decay behavior (12h half life)."""
    now = datetime.now(timezone.utc)

    # 0 hours old: ~100
    f0 = FreshnessEngine.calculate_freshness(now, reference_time=now)
    assert f0 == 100.0

    # 12 hours old: ~50
    f12 = FreshnessEngine.calculate_freshness(now - timedelta(hours=12), reference_time=now)
    assert 48.0 <= f12 <= 52.0

    # 24 hours old: ~25
    f24 = FreshnessEngine.calculate_freshness(now - timedelta(hours=24), reference_time=now)
    assert 23.0 <= f24 <= 27.0

    # 48 hours old: ~6
    f48 = FreshnessEngine.calculate_freshness(now - timedelta(hours=48), reference_time=now)
    assert f48 < 10.0


def test_velocity_calculation(db_session, sample_source):
    """Rapid accumulation of recent articles yields high velocity score."""
    now = datetime.now(timezone.utc)
    cluster = StoryCluster(
        canonical_title="Breaking Tech Story",
        category="technology",
        first_seen_at=now - timedelta(hours=2),
        last_seen_at=now,
    )
    db_session.add(cluster)
    db_session.commit()

    # Add 4 articles published in last 2 hours
    for i in range(4):
        art = Article(
            source_id=sample_source.id,
            title=f"Breaking Tech Update {i}",
            url=f"https://example.com/b/{i}",
            canonical_url=f"https://example.com/b/{i}",
            published_at=now - timedelta(minutes=i * 20),
            content_hash=f"b_hash_{i}",
        )
        db_session.add(art)
        db_session.commit()
        db_session.add(StoryClusterArticle(story_cluster_id=cluster.id, article_id=art.id))
    db_session.commit()

    v = VelocityEngine.calculate_velocity(db_session, cluster, reference_time=now)
    assert v >= 50.0
    assert v <= 100.0


# ==========================================
# 6. RELEVANCE & TRENDING TESTS
# ==========================================

def test_relevance_category_weighting(db_session):
    """World/politics categories receive higher base relevance than sports/general."""
    cl_world = StoryCluster(canonical_title="T1", category="world")
    cl_gen = StoryCluster(canonical_title="T2", category="general")
    db_session.add_all([cl_world, cl_gen])
    db_session.commit()

    rel_world = RelevanceEngine.calculate_relevance(db_session, cl_world)
    rel_gen = RelevanceEngine.calculate_relevance(db_session, cl_gen)
    assert rel_world > rel_gen


def test_trending_formula_and_bounds(db_session, sample_source):
    """Trending score obeys documented weights and clamps to [0, 100]."""
    cluster = StoryCluster(
        canonical_title="Trending Test Story",
        category="world",
        first_seen_at=datetime.now(timezone.utc),
        last_seen_at=datetime.now(timezone.utc),
    )
    db_session.add(cluster)
    db_session.commit()

    art = Article(
        source_id=sample_source.id,
        title="Trending Test Story",
        url="https://example.com/t1",
        canonical_url="https://example.com/t1",
        published_at=datetime.now(timezone.utc),
        content_hash="t_hash_1",
    )
    db_session.add(art)
    db_session.commit()
    db_session.add(StoryClusterArticle(story_cluster_id=cluster.id, article_id=art.id))
    db_session.commit()

    scored = TrendingEngine.score_cluster(db_session, cluster)
    assert 0.0 <= scored.trending_score <= 100.0
    assert scored.scoring_metadata is not None
    meta = json.loads(scored.scoring_metadata)
    assert meta["weights"]["velocity"] == 0.30
    assert meta["weights"]["freshness"] == 0.25
    assert meta["weights"]["corroboration"] == 0.25
    assert meta["weights"]["relevance"] == 0.20


# ==========================================
# 7. STORY STATE MACHINE TESTS
# ==========================================

def test_story_state_transitions():
    """State machine transitions correctly based on measurable metrics."""
    # 1. Stale state when freshness is very low
    assert TrendingEngine.evaluate_state(trending_score=50.0, velocity=10.0, freshness=5.0, article_count=2, source_count=2) == "STALE"

    # 2. Peak state for high velocity, high trending, multi-source
    assert TrendingEngine.evaluate_state(trending_score=85.0, velocity=70.0, freshness=90.0, article_count=5, source_count=3) == "PEAK"

    # 3. Trending state
    assert TrendingEngine.evaluate_state(trending_score=70.0, velocity=40.0, freshness=80.0, article_count=3, source_count=2) == "TRENDING"

    # 4. Cooling state
    assert TrendingEngine.evaluate_state(trending_score=40.0, velocity=10.0, freshness=25.0, article_count=2, source_count=1) == "COOLING"

    # 5. Rising state
    assert TrendingEngine.evaluate_state(trending_score=50.0, velocity=35.0, freshness=60.0, article_count=2, source_count=1) == "RISING"

    # 6. Emerging default
    assert TrendingEngine.evaluate_state(trending_score=25.0, velocity=10.0, freshness=95.0, article_count=1, source_count=1) == "EMERGING"


# ==========================================
# 8. PIPELINE & IDEMPOTENCY TESTS
# ==========================================

def test_pipeline_idempotency_repeated_processing(db_session, sample_source):
    """Running intelligence pipeline twice on the same articles does not duplicate clusters or entities."""
    now = datetime.now(timezone.utc)
    art1 = Article(
        source_id=sample_source.id,
        title="Summit Reaches Historic Climate Accord in Geneva",
        url="https://source-a.example.com/p1",
        canonical_url="https://source-a.example.com/p1",
        published_at=now,
        content_hash="pipe_hash_1",
        category="world",
    )
    art2 = Article(
        source_id=sample_source.id,
        title="Historic Climate Accord in Geneva Announced",
        url="https://source-b.example.com/p2",
        canonical_url="https://source-b.example.com/p2",
        published_at=now + timedelta(minutes=10),
        content_hash="pipe_hash_2",
        category="world",
    )
    db_session.add_all([art1, art2])
    db_session.commit()

    pipeline = IntelligencePipeline(db_session)

    # First run
    res1 = pipeline.run_pipeline()
    cluster_count_1 = db_session.query(StoryCluster).count()
    entity_count_1 = db_session.query(Entity).count()
    link_count_1 = db_session.query(StoryClusterArticle).count()

    # Second run
    res2 = pipeline.run_pipeline()
    cluster_count_2 = db_session.query(StoryCluster).count()
    entity_count_2 = db_session.query(Entity).count()
    link_count_2 = db_session.query(StoryClusterArticle).count()

    assert cluster_count_1 == cluster_count_2
    assert entity_count_1 == entity_count_2
    assert link_count_1 == link_count_2
    assert link_count_1 == 2


def test_pipeline_new_article_joins_existing_cluster(db_session, sample_source):
    """Adding a third related article joins the existing cluster rather than creating a new one."""
    now = datetime.now(timezone.utc)
    art1 = Article(
        source_id=sample_source.id,
        title="Global Summit Concludes with Historic Clean Energy Pact",
        url="https://source-a.example.com/join1",
        canonical_url="https://source-a.example.com/join1",
        published_at=now,
        content_hash="join_hash_1",
        category="world",
    )
    db_session.add(art1)
    db_session.commit()

    pipeline = IntelligencePipeline(db_session)
    c1 = pipeline.process_article(art1)
    assert db_session.query(StoryCluster).count() == 1

    art2 = Article(
        source_id=sample_source.id,
        title="Historic Clean Energy Pact Concluded at Global Summit",
        url="https://source-b.example.com/join2",
        canonical_url="https://source-b.example.com/join2",
        published_at=now + timedelta(minutes=30),
        content_hash="join_hash_2",
        category="world",
    )
    db_session.add(art2)
    db_session.commit()

    c2 = pipeline.process_article(art2)
    assert db_session.query(StoryCluster).count() == 1
    assert c1.id == c2.id
    assert c2.article_count == 2


# ==========================================
# 9. API INTELLIGENCE ENDPOINTS
# ==========================================

def test_api_intelligence_endpoints(test_client, db_session, sample_source):
    """Test /api/intelligence/stories, /trending, /stories/{id}, /entities."""
    now = datetime.now(timezone.utc)
    art = Article(
        source_id=sample_source.id,
        title="Apple Launches Revolutionary Neural Glass in London",
        url="https://apple.example.com/glass",
        canonical_url="https://apple.example.com/glass",
        published_at=now,
        content_hash="api_int_hash",
        category="technology",
    )
    db_session.add(art)
    db_session.commit()

    pipeline = IntelligencePipeline(db_session)
    cluster = pipeline.process_article(art)

    # 1. GET /api/intelligence/stories
    res = test_client.get("/api/intelligence/stories")
    assert res.status_code == 200
    stories = res.json()
    assert len(stories) >= 1
    assert stories[0]["canonical_title"] == art.title

    # 2. GET /api/intelligence/trending
    res = test_client.get("/api/intelligence/trending")
    assert res.status_code == 200
    trending = res.json()
    assert len(trending) >= 1
    assert "trending_score" in trending[0]

    # 3. GET /api/intelligence/stories/{id}
    res = test_client.get(f"/api/intelligence/stories/{cluster.id}")
    assert res.status_code == 200
    detail = res.json()
    assert detail["id"] == cluster.id
    assert len(detail["articles"]) == 1
    assert len(detail["entities"]) >= 1

    # 4. GET /api/intelligence/entities
    res = test_client.get("/api/intelligence/entities")
    assert res.status_code == 200
    assert len(res.json()) >= 1
