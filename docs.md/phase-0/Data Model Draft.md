# Phase 0 — Data Model Draft

**Date:** 2026-06-27  
**Purpose:** Task 0.6 — Define unified review schema and related entities aligned with `System Architecture.md`.

---

## Entity Relationship Overview

```mermaid
erDiagram
    RAW_REVIEW {
        uuid id PK
        string platform
        string source_url
        json raw_payload
        datetime collected_at
    }

    REVIEW {
        uuid id PK
        uuid raw_review_id FK
        string platform
        text content
        int rating
        datetime posted_at
        string anonymized_author
        string sentiment
        string language
        boolean is_discovery_related
    }

    REVIEW_EMBEDDING {
        uuid review_id PK_FK
        blob embedding_vector
        datetime indexed_at
    }

    THEME {
        uuid id PK
        string name
        text description
        int review_count
        string overall_sentiment
        float confidence_score
        datetime date_range_start
        datetime date_range_end
        json top_keywords
    }

    REVIEW_THEME {
        uuid review_id FK
        uuid theme_id FK
        float membership_score
    }

    INSIGHT {
        uuid id PK
        uuid theme_id FK
        string category
        text summary
        int supporting_review_count
        float opportunity_score
        datetime generated_at
    }

    QUOTE {
        uuid id PK
        uuid review_id FK
        uuid theme_id FK
        text excerpt
        string source_platform
    }

    RAW_REVIEW ||--o| REVIEW : "processed into"
    REVIEW ||--o| REVIEW_EMBEDDING : "has"
    REVIEW ||--o{ REVIEW_THEME : "belongs to"
    THEME ||--o{ REVIEW_THEME : "contains"
    THEME ||--o{ INSIGHT : "generates"
    REVIEW ||--o{ QUOTE : "provides"
    THEME ||--o{ QUOTE : "includes"
```

---

## Table Definitions

### `raw_reviews`

Stores unmodified collector output for audit and reprocessing.

| Column | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | Yes | Primary key |
| `platform` | VARCHAR(50) | Yes | `play_store`, `app_store`, `reddit`, `spotify_community` |
| `external_id` | VARCHAR(255) | Yes | Platform-native ID |
| `source_url` | TEXT | No | Original URL |
| `raw_payload` | JSON | Yes | Full collector response |
| `collected_at` | TIMESTAMP | Yes | When record was fetched |

**Unique constraint:** `(platform, external_id)`

---

### `reviews`

Clean, anonymized, normalized records used for analysis and search.

| Column | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | Yes | Primary key |
| `raw_review_id` | UUID | Yes | FK → `raw_reviews.id` |
| `platform` | VARCHAR(50) | Yes | Source platform |
| `content` | TEXT | Yes | Cleaned review/discussion text |
| `title` | TEXT | No | Review title (App Store) or post title (Reddit/Forum) |
| `rating` | INTEGER | No | Star rating 1–5 (app stores only) |
| `posted_at` | TIMESTAMP | Yes | Original post/review date (UTC) |
| `anonymized_author` | VARCHAR(50) | Yes | e.g. `user_a1b2c3` |
| `sentiment` | VARCHAR(20) | No | `positive`, `negative`, `neutral` — filled in Phase 4 |
| `language` | VARCHAR(10) | Yes | ISO 639-1, default `en` |
| `is_discovery_related` | BOOLEAN | Yes | Passed keyword filter |
| `word_count` | INTEGER | Yes | For quality filtering |
| `created_at` | TIMESTAMP | Yes | Processing timestamp |

**Indexes:** `posted_at`, `platform`, `sentiment`, `is_discovery_related`

---

### `review_embeddings`

Search index — one embedding vector per review.

| Column | Type | Required | Description |
|---|---|---|---|
| `review_id` | UUID | Yes | PK/FK → `reviews.id` |
| `embedding_model` | VARCHAR(100) | Yes | e.g. `all-MiniLM-L6-v2` |
| `embedding_vector` | BLOB | Yes | Serialized float32 array (384 dims) |
| `indexed_at` | TIMESTAMP | Yes | When embedding was generated |

---

### `themes`

| Column | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | Yes | Primary key |
| `name` | VARCHAR(255) | Yes | Human-readable theme label |
| `description` | TEXT | No | Optional longer description |
| `review_count` | INTEGER | Yes | Supporting review count |
| `overall_sentiment` | VARCHAR(20) | Yes | Aggregated sentiment |
| `confidence_score` | FLOAT | No | Cluster cohesion score (0–1) |
| `date_range_start` | TIMESTAMP | Yes | Earliest review in cluster |
| `date_range_end` | TIMESTAMP | Yes | Latest review in cluster |
| `top_keywords` | JSON | Yes | e.g. `["discover weekly", "repetitive", "algorithm"]` |
| `created_at` | TIMESTAMP | Yes | Analysis run timestamp |

---

### `review_themes`

Many-to-many join between reviews and themes.

| Column | Type | Required | Description |
|---|---|---|---|
| `review_id` | UUID | Yes | FK → `reviews.id` |
| `theme_id` | UUID | Yes | FK → `themes.id` |
| `membership_score` | FLOAT | No | Cluster assignment probability |

**Primary key:** `(review_id, theme_id)`

---

### `insights`

Structured product discovery outputs.

| Column | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | Yes | Primary key |
| `theme_id` | UUID | Yes | FK → `themes.id` |
| `category` | VARCHAR(50) | Yes | `pain_point`, `behavior`, `segmentation`, `opportunity` |
| `summary` | TEXT | Yes | Evidence-backed insight statement |
| `supporting_review_count` | INTEGER | Yes | Number of backing reviews |
| `opportunity_score` | FLOAT | No | frequency × sentiment weight |
| `generated_at` | TIMESTAMP | Yes | When insight was generated |

---

### `quotes`

Representative verbatim excerpts linked to themes and reviews.

| Column | Type | Required | Description |
|---|---|---|---|
| `id` | UUID | Yes | Primary key |
| `review_id` | UUID | Yes | FK → `reviews.id` |
| `theme_id` | UUID | Yes | FK → `themes.id` |
| `excerpt` | TEXT | Yes | Verbatim quote (unaltered) |
| `source_platform` | VARCHAR(50) | Yes | Platform attribution |
| `is_representative` | BOOLEAN | Yes | Selected as top quote for theme |

---

## API Response Shapes (Preview)

### Search Result Object

```json
{
  "review_id": "uuid",
  "platform": "reddit",
  "content_excerpt": "Discover Weekly keeps giving me the same artists...",
  "posted_at": "2025-11-14T08:22:00Z",
  "sentiment": "negative",
  "relevance_score": 0.87,
  "source_url": "https://reddit.com/r/spotify/..."
}
```

### Theme Object

```json
{
  "theme_id": "uuid",
  "name": "Repetitive Discover Weekly Recommendations",
  "review_count": 142,
  "overall_sentiment": "negative",
  "confidence_score": 0.81,
  "date_range": { "start": "2024-03-01", "end": "2025-11-20" },
  "top_keywords": ["discover weekly", "same songs", "repetitive"],
  "representative_quotes": ["...", "..."]
}
```

---

## Platform Enum Values

| Value | Description |
|---|---|
| `play_store` | Google Play Store |
| `app_store` | Apple App Store |
| `reddit` | Reddit posts and comments |
| `spotify_community` | Spotify Community forum |
| `social_media` | Optional — Twitter, YouTube, etc. |

---

## Exit Criteria

- [x] Unified review schema defined
- [x] Raw vs. processed separation documented
- [x] Theme, insight, and quote entities defined
- [x] Search index (embeddings) table defined
- [x] Schema aligned with `System Architecture.md` conceptual model
