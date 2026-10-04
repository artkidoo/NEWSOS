"""Verification script testing complete clean database lifecycle:
Phase 1 migration -> Phase 2 migration -> seed test data -> ingestion -> intelligence processing -> clustering -> scoring -> API retrieval.
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.session import get_db
from app.main import app
from app.models.article import Article
from app.models.enums import SourceType, TrustLevel
from app.models.intelligence import StoryCluster
from app.models.source import Source
from app.services.intelligence.pipeline import IntelligencePipeline


def run_clean_test():
    db_file = "clean_test.db"
    if os.path.exists(db_file):
        os.remove(db_file)

    print(f"[*] Testing Clean Database Pipeline on: {db_file}")

    # 1. Run migrations 0001 -> 0002
    alembic_cfg = Config("alembic.ini")
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_file}")

    print("[*] Running Alembic migration upgrade 0001 -> 0002 -> head...")
    command.upgrade(alembic_cfg, "head")

    # 2. Connect engine
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()

    # 3. Seed source data
    print("[*] Seeding news sources...")
    src1 = Source(
        name="Global News Network",
        url="https://gnn.example.com",
        feed_url="https://gnn.example.com/rss",
        source_type=SourceType.RSS,
        category="world",
        trust_level=TrustLevel.HIGH,
        enabled=True,
    )
    src2 = Source(
        name="Tech Radar Dispatch",
        url="https://techradar.example.com",
        feed_url="https://techradar.example.com/rss",
        source_type=SourceType.RSS,
        category="technology",
        trust_level=TrustLevel.VERIFIED,
        enabled=True,
    )
    db.add_all([src1, src2])
    db.commit()

    # 4. Ingest sample articles
    print("[*] Inserting raw normalized articles...")
    now = datetime.now(timezone.utc)
    art1 = Article(
        source_id=src1.id,
        title="International Climate Treaty Ratified in Geneva",
        url="https://gnn.example.com/world/climate-treaty-1",
        canonical_url="https://gnn.example.com/world/climate-treaty-1",
        published_at=now,
        content_hash="clean_hash_1",
        category="world",
    )
    art2 = Article(
        source_id=src2.id,
        title="Geneva Summit Concludes With Historic Climate Treaty",
        url="https://techradar.example.com/news/climate-treaty-2",
        canonical_url="https://techradar.example.com/news/climate-treaty-2",
        published_at=now,
        content_hash="clean_hash_2",
        category="world",
    )
    db.add_all([art1, art2])
    db.commit()

    # 5. Process Intelligence Pipeline
    print("[*] Running IntelligencePipeline...")
    pipeline = IntelligencePipeline(db)
    res = pipeline.run_pipeline()
    print(f"    Evaluated: {res['articles_evaluated']}, Created: {res['clusters_created']}, Scored: {res['clusters_scored']}")

    # 6. Verify clustering
    clusters = db.query(StoryCluster).all()
    assert len(clusters) == 1, f"Expected 1 cluster, found {len(clusters)}"
    cluster = clusters[0]
    assert cluster.article_count == 2
    assert cluster.source_count == 2
    assert cluster.trending_score > 0
    print(f"[+] Story Cluster created successfully: '{cluster.canonical_title}'")
    print(f"    Trending Score: {cluster.trending_score} (State: {cluster.status})")

    # 7. Test API retrieval via TestClient
    print("[*] Verifying API retrieval...")
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        resp = client.get("/api/intelligence/stories")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["article_count"] == 2

        resp_trend = client.get("/api/intelligence/trending")
        assert resp_trend.status_code == 200
        assert len(resp_trend.json()) == 1

        resp_detail = client.get(f"/api/intelligence/stories/{cluster.id}")
        assert resp_detail.status_code == 200
        detail = resp_detail.json()
        assert len(detail["articles"]) == 2
        print(f"[+] API Retrieval verified successfully: {len(detail['articles'])} articles, {len(detail['entities'])} entities")

    app.dependency_overrides.clear()
    db.close()
    engine.dispose()
    if os.path.exists(db_file):
        os.remove(db_file)

    print("[SUCCESS] All clean database lifecycle checks passed.")


if __name__ == "__main__":
    run_clean_test()
