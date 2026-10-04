# NEWSROOM OS

Production-grade editorial news automation platform: Discovery, Normalization, Deduplication, and Story Intelligence.

## Key Features

### Phase 1 — Ingestion & Normalization
* **Syndicated Feed Discovery:** Parses RSS 2.0, Atom 1.0, and media enclosures with custom headers and timeouts.
* **Canonical Normalization:** Strips tracking query parameters (`utm_*`, `fbclid`), sanitizes HTML payloads, and generates deterministic SHA-256 content hashes.
* **Deduplication Engine:** Exact content hash matching, canonical URL detection, and title lexical similarity checks.
* **Audit Trail:** Comprehensive tracking of feed runs, articles ingested, and skipped duplicates.

### Phase 2 — Story Intelligence & Trending Engine
* **Story Clustering:** Bounded 48-hour candidate search clustering articles into distinct real-world events.
* **Anti-Spurious Clustering:** Prevents false cluster mergers of articles sharing a common entity name on different events.
* **Named Entity Extraction:** High-precision deterministic NLP extraction of people, organizations, locations, and brands.
* **Multi-Signal Scoring:**
  - **Velocity (30%):** Rate of article accumulation and recent momentum acceleration.
  - **Freshness (25%):** Deterministic 12-hour exponential half-life decay.
  - **Corroboration (25%):** Publisher breadth and trust weighting ("Reported by X sources").
  - **Relevance (20%):** Editorial topic weighting and entity density.
* **Story Lifecycle State Machine:** Dynamic bidirectional transitions across `EMERGING`, `RISING`, `TRENDING`, `PEAK`, `COOLING`, and `STALE`.
* **Idempotency:** Re-processing identical feeds and articles does not duplicate clusters, entities, or linkages.
* **Editorial Dashboard:** Live React 19 UI with real-time score explainability and evidence inspection.

## Quick Start

### 1. Run Tests
```bash
# Complete test suite (55 tests)
python3 -m pytest -v

# Phase 1 tests only (29 tests)
python3 -m pytest tests/test_sources.py tests/test_database.py tests/test_feed_parser.py tests/test_normalization.py tests/test_deduplication.py tests/test_idempotency.py tests/test_api.py -v

# Phase 2 tests only (26 tests)
python3 -m pytest tests/test_intelligence.py tests/test_clean_db_integration.py -v
```

### 2. Verify Clean Database Pipeline
```bash
python3 scripts/test_clean_database.py
```

### 3. Run Linter & Type Check
```bash
python3 -m ruff check app tests scripts
npm run lint
npm run build
```
