"""CLI script to run feed polling and intelligence pipeline."""

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.db.session import SessionLocal
from app.models.source import Source
from app.services.ingestion.engine import IngestionEngine
from app.services.intelligence.pipeline import IntelligencePipeline


def run():
    db = SessionLocal()
    try:
        sources = db.query(Source).filter(Source.enabled == True).all()
        print(f"[*] Starting ingestion for {len(sources)} sources...")
        engine = IngestionEngine(db)
        for s in sources:
            res = engine.ingest_source(s)
            print(f"    Source: {s.name} -> Found: {res.get('found', 0)}, Ingested: {res.get('ingested', 0)}, Skipped: {res.get('skipped', 0)}")

        print("[*] Running Story Intelligence Pipeline...")
        pipeline = IntelligencePipeline(db)
        intel_res = pipeline.run_pipeline()
        print("[+] Intelligence Pipeline Complete:")
        print(f"    Articles Evaluated: {intel_res['articles_evaluated']}")
        print(f"    Clusters Created:   {intel_res['clusters_created']}")
        print(f"    Clusters Updated:   {intel_res['clusters_updated']}")
        print(f"    Entities Extracted: {intel_res['entities_extracted']}")
        print(f"    Clusters Scored:    {intel_res['clusters_scored']}")
    finally:
        db.close()


if __name__ == "__main__":
    run()
