# NEWSROOM OS — Story Intelligence & Trending Engine Specification

## 1. Overview
The Story Intelligence & Trending Engine (Phase 2) processes normalized news articles from syndicated feeds, clusters articles into distinct real-world events, extracts named entities, calculates multi-dimensional editorial signals (Velocity, Freshness, Corroboration, Relevance), assigns a composite trending score, and manages the story lifecycle via a deterministic state machine.

---

## 2. Clustering Algorithm & Candidate Search Strategy
* **Candidate Window Filter:** Bounded search queries only evaluate existing clusters within a 48-hour window (`article.published_at - 48h <= cluster.last_seen_at <= article.published_at + 48h`). This eliminates $O(N^2)$ all-pairs comparisons.
* **Category Partitioning:** Articles in specific categories (e.g. `technology`, `business`) are compared only with clusters in the matching category or `general`.
* **Lexical Jaccard Metric:** Tokenizes titles into lower-case alphanumeric terms ($\ge 3$ characters), filtering out general headline stopwords.
* **Anti-Spurious Guard:** Prevents articles from clustering merely because they share a single entity name (e.g. "Apple launches new iPhone" vs "Apple reports quarterly earnings" or "Artist X releases album" vs "Artist X attends football match"). If the token intersection has $\le 1$ word and union is large, the similarity returns $0.0$.
* **Threshold:** Similarity threshold of $\ge 0.35$ required to join an existing cluster. Otherwise, a new StoryCluster is seeded.

---

## 3. Named Entity Extraction
* **Method:** High-precision deterministic NLP extraction utilizing known entity dictionaries (organizations, brands, countries, cities) combined with title-case multi-word proper noun extraction.
* **Normalization:** All entity names are normalized into snake_case identifiers (e.g., `apple`, `united_nations`, `tokyo`) to guarantee idempotency and avoid duplicates.
* **Types:** `person`, `organization`, `location`, `country`, `brand`.
* **Database Tracking:** `entities`, `article_entities` (confidence score, extraction method), and `story_cluster_entities` (mention counts).

---

## 4. Signal Scoring Formulas

### 4.1. Velocity (Weight: 0.30)
Measures the rate of article accumulation and recent acceleration:
* Evaluates articles published within the last 6-hour window versus the prior 6-hour window.
* Acceleration factor: $\frac{\text{recent\_count} + 1}{\text{prev\_count} + 1}$.
* Normalized to range $[0.0, 100.0]$.

### 4.2. Freshness (Weight: 0.25)
Deterministic exponential time-decay based on the age of the latest article in the cluster (`last_seen_at`):
$$\text{Freshness} = 100 \times \left(0.5\right)^{\frac{\text{age\_hours}}{12.0}}$$
* Half-life ($T_{1/2}$) is 12 hours.
* Brand new stories score 100.0; at 12 hours: 50.0; at 24 hours: 25.0; at 48 hours: 6.25.
* Normalized to range $[0.0, 100.0]$.

### 4.3. Corroboration (Weight: 0.25)
Measures reporting breadth across independent publishers:
* Distinct publishers: Multiple articles from one publisher count as 1 source.
* Publisher trust levels are weighted: `LOW` (0.5), `MEDIUM` (1.0), `HIGH` (1.5), `VERIFIED` (2.0).
* Formula: $\text{score} = \min(100.0, \max(10.0, \frac{\sum \text{trust}}{5.0} \times 100))$.
* Label format: `"Reported by X independent sources"`. Never described as "confirmed truth".

### 4.4. Relevance (Weight: 0.20)
Measures category importance and entity prominence:
* Category baseline: `world` (85), `politics` (85), `technology` (80), `business` (80), `science` (75), `general` (50).
* Entity bonus: $+3.0$ points per distinct linked entity (capped at $+15.0$).
* Normalized to range $[0.0, 100.0]$.

---

## 5. Composite Trending Score Formula
$$\text{Trending Score} = (\text{Velocity} \times 0.30) + (\text{Freshness} \times 0.25) + (\text{Corroboration} \times 0.25) + (\text{Relevance} \times 0.20)$$
* Clamped strictly between $0.0$ and $100.0$.
* Explainability: The API and database expose full scoring metadata including individual components and weights.

---

## 6. Story State Machine
The lifecycle transitions bidirectionally according to measurable signals:
* `STALE`: Freshness $\le 10.0$ (inactivity $> 40$ hours).
* `PEAK`: Trending score $\ge 80.0$, Velocity $\ge 60.0$, and Sources $\ge 2$.
* `TRENDING`: Trending score $\ge 65.0$ and Articles $\ge 2$.
* `COOLING`: Freshness $\le 35.0$ and Velocity $\le 20.0$.
* `RISING`: Trending score $\ge 45.0$ or Velocity $\ge 30.0$.
* `EMERGING`: Default initial state for nascent coverage.

Stories can move back up from `COOLING` to `RISING` or `TRENDING` if breaking updates arrive.

---

## 7. Known Limitations
1. **Lexical Clustering:** Uses token-based Jaccard similarity; semantic embeddings (e.g. text-embedding-004) would improve handling of metaphorical headlines.
2. **Deterministic Entity Extraction:** Rules-based and dictionary-driven; lacks deep transformer NER models.
