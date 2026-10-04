# NEWSROOM OS — Master Technical Specification

## System Vision
NEWSROOM OS is an editorial news automation platform designed to ingest, normalize, deduplicate, cluster, score, and surface real-time trending news stories for newsroom editors.

---

## Phase Status Overview
* **Phase 1: Ingestion, Normalization, and Deduplication** — COMPLETE & VERIFIED (29 tests passing).
  - RSS 2.0, Atom 1.0, and JSON Feed discovery and parsing.
  - Tracking parameter stripping (UTM, fbclid, etc.) and HTML sanitization.
  - SHA-256 content hashing and Jaccard title near-duplicate detection.
  - Full audit logging with `IngestionRun` tracking.
* **Phase 2: Story Intelligence & Trending Engine** — COMPLETE & VERIFIED (26 tests passing).
  - Bounded 48h candidate search clustering with anti-spurious entity guards.
  - Deterministic named entity extraction and disambiguation.
  - Source-weighted corroboration scoring ("Reported by X sources").
  - Exponential time decay freshness ($T_{1/2} = 12\text{h}$).
  - Rolling window coverage velocity with acceleration factor.
  - Category and entity editorial relevance.
  - Composite trending score: $(V \times 0.30) + (F \times 0.25) + (C \times 0.25) + (R \times 0.20)$.
  - Bidirectional 6-state Story Lifecycle State Machine (`EMERGING`, `RISING`, `TRENDING`, `PEAK`, `COOLING`, `STALE`).
  - Score explainability and audit trail.
  - Idempotent pipeline execution.
* **Phase 3: Editorial Desk & Workflow Engine** — PENDING (Do not begin until Phase 2 signed off).

---

## Technology Stack
* **Backend:** Python 3.10+, FastAPI 0.110+, SQLAlchemy 2.0+, Alembic 1.13+, SQLite / PostgreSQL.
* **Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, Lucide Icons.
* **Testing:** Pytest 9+, pytest-asyncio, Alembic migration test suite.
* **Linter & Code Quality:** Ruff 0.3+, tsc --noEmit.
