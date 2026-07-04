# Phase 0 — Tech Stack Selection

**Date:** 2026-06-27  
**Purpose:** Finalize language, frameworks, libraries, and project structure for Phases 1–8.

---

## Selected Stack

| Layer | Technology | Version | Rationale |
|---|---|---|---|
| **Language** | Python | 3.11+ | Rich NLP ecosystem; fast prototyping |
| **Backend API** | FastAPI | ≥ 0.104 | Async, auto OpenAPI docs, type hints |
| **Database** | SQLite (dev) → PostgreSQL (optional prod) | — | Zero-config for graduation project |
| **ORM** | SQLAlchemy | ≥ 2.0 | Mature; supports SQLite and PostgreSQL |
| **Dashboard** | Streamlit | ≥ 1.28 | Rapid UI for research dashboard; minimal frontend code |
| **NLP — Sentiment** | Hugging Face `transformers` | ≥ 4.36 | `twitter-roberta-base-sentiment-latest` |
| **NLP — Embeddings** | `sentence-transformers` | ≥ 2.2 | `all-MiniLM-L6-v2` |
| **NLP — Clustering** | BERTopic | ≥ 0.16 | Theme discovery |
| **Search** | NumPy + `rank-bm25` | — | Hybrid semantic + keyword search |
| **Data Collection** | See below | — | Platform-specific libraries |
| **Report Export** | Markdown + `weasyprint` or `pdfkit` | — | Insight report PDF export |
| **Testing** | pytest | ≥ 7.4 | Unit and API tests |
| **Linting** | ruff | ≥ 0.1 | Fast Python linter |

---

## Data Collection Libraries

| Source | Library | Install |
|---|---|---|
| Google Play Store | `google-play-scraper` | `pip install google-play-scraper` |
| Apple App Store | `app-store-scraper` | `pip install app-store-scraper` |
| Reddit | `praw` | `pip install praw` |
| Spotify Community | `httpx` or `requests` | Direct Discourse JSON API calls |

---

## Project Structure (Phase 1 Target)

```
review-discovery-engine/
├── collectors/              # Phase 2 — data collection scripts
│   ├── play_store.py
│   ├── app_store.py
│   ├── reddit_collector.py
│   └── spotify_community.py
├── processing/              # Phase 3 — clean, anonymize, normalize
│   ├── pipeline.py
│   ├── anonymizer.py
│   └── pii_scanner.py
├── analysis/                # Phase 4 — NLP pipeline
│   ├── sentiment.py
│   ├── embeddings.py
│   ├── themes.py
│   └── insights.py
├── api/                     # Phase 5 — FastAPI backend
│   ├── main.py
│   ├── routes/
│   └── services/
├── dashboard/               # Phase 6 — Streamlit app
│   └── app.py
├── reports/                 # Phase 7 — report generator
│   └── generator.py
├── models/                  # SQLAlchemy models
│   └── schema.py
├── utils/                   # Shared utilities
│   ├── logging.py
│   └── config.py
├── data/                    # Local data (gitignored)
│   ├── raw/
│   └── processed/
├── tests/
├── docs.md/
├── requirements.txt
├── .env.example
└── README.md
```

---

## Environment Variables (`.env.example` preview)

```env
# Reddit API (create app at reddit.com/prefs/apps)
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=review-discovery-engine/1.0 by your_reddit_username

# Database
DATABASE_URL=sqlite:///./data/reviews.db

# NLP
EMBEDDING_MODEL=all-MiniLM-L6-v2
SENTIMENT_MODEL=cardiffnlp/twitter-roberta-base-sentiment-latest

# API
API_HOST=0.0.0.0
API_PORT=8000
```

---

## Deployment Approach

| Environment | Setup |
|---|---|
| Local development | Python venv + SQLite + Streamlit + FastAPI |
| Demo / submission | Single machine; run API and dashboard as two processes |
| Optional cloud | Railway / Render free tier with PostgreSQL |

No Docker required for graduation scope — keep setup simple and documented in README.

---

## Alternatives Considered

| Component | Alternative | Why Not Selected |
|---|---|---|
| Frontend | React + Chart.js | More setup time; Streamlit sufficient for research dashboard |
| Database | MongoDB | Relational model fits structured reviews + themes better |
| API | Flask | FastAPI preferred for auto-docs and type safety |
| NLP cloud | OpenAI API | Cost and privacy; local models sufficient for 5k records |
| Search | Elasticsearch | Over-engineered for project scale |

---

## Exit Criteria

- [x] Language and framework selected
- [x] NLP libraries aligned with NLP Tool Selection doc
- [x] Collection libraries identified per source
- [x] Project folder structure defined for Phase 1
- [x] Environment variable template planned
