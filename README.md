# Spotify Review Discovery Engine

AI-powered platform that aggregates publicly available user feedback about Spotify's music discovery experience, analyzes it with NLP, and surfaces structured, evidence-backed insights for product research.

## Project Status

| Phase | Name | Status |
|---|---|---|
| 0 | Research & Planning | Complete |
| 1 | Foundation | Complete |
| 2 | Data Collection | Complete |
| 3 | Data Processing | Complete |
| 4 | Embedding & Themes | Complete |
| 5 | Segments & Needs | Complete |
| 6 | Validation & Weekly Pulse | Complete |
| 7 | API & Search (RAG chat) | Complete |
| 8 | Dashboard | Complete |
| 9 | Integration & Delivery | Complete |

See [Implementation Plan](docs.md/implementationplan.md) for phase details and [Demo Script](docs.md/demo_script.md) for a 10–15 minute walkthrough.

## Documentation

- [Problem Statement](docs.md/Problem%20Statement.md)
- [System Architecture](System%20Architecture.md)
- [Phase-Wise Plan](Phase%20wise%20architecture.md)
- [Implementation Plan](docs.md/implementationplan.md)
- [Demo Script](docs.md/demo_script.md)
- [Context Token Usage (Cursor)](docs.md/Context-Token-Usage.md)
- [Learning Log](docs.md/Learning%20Log.md)
- [Phase 0 Research](docs.md/phase-0/Phase%200%20Summary.md)

## Requirements

- Python 3.11+
- pip

## Quick Start (Step-by-Step)

### Step 1: Set Up Python Environment

```bash
# Navigate to the project directory
cd "Graduation Project"

# Create a Python virtual environment
python -m venv .venv

# Activate the virtual environment
# On Windows:
.venv\Scripts\activate

# On macOS/Linux:
source .venv/bin/activate
```

### Step 2: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 3: Start PostgreSQL (with pgvector)

```bash
docker compose up -d
```

Copy environment variables and adjust if needed:

```bash
copy .env.example .env
```

Default connection:

`postgresql+psycopg://postgres:postgres@localhost:5432/review_discovery`

### Step 4: Initialize the Database

```bash
python scripts/init_db.py
```

Expected output: `Database initialized at postgresql+psycopg://...`

#### Migrating existing SQLite + Chroma data (optional)

If you already have `data/reviews.db` and `data/chroma/`:

```bash
pip install chromadb
python scripts/migrate_sqlite_chroma_to_postgres.py
```

### Step 5: Start the API Backend (Terminal 1)

```bash
.venv\Scripts\python -m uvicorn api.main:app --reload
```

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health
- **RAG Chat**: `GET /api/chat?q=your+question&platform=play_store`

### Step 6: Start the Dashboard (Terminal 2)

```bash
.venv\Scripts\python -m streamlit run dashboard/app.py
```

Visit **http://localhost:8501**

### Step 7: Validate Integration (Phase 9)

```bash
# Full check (API must be running)
.venv\Scripts\python scripts/validate_integration.py

# Database privacy audit only
.venv\Scripts\python scripts/validate_integration.py --offline
```

---

## Running Tests

Requires PostgreSQL with pgvector (use `docker compose up -d` and set `TEST_DATABASE_URL` if needed):

```bash
pytest tests/ -v
```

---

## Data Pipeline

```bash
python scripts/run_collection.py
python scripts/run_processing.py
python scripts/run_analysis.py
python scripts/run_pulse.py --dry-run
```

| Script | Purpose |
|---|---|
| `run_collection.py` | Collect public reviews from Play Store, App Store, community |
| `run_processing.py` | Clean, anonymize, deduplicate |
| `run_analysis.py` | Sentiment, themes, embeddings, pgvector index |
| `run_pulse.py` | Weekly pulse generation and Docs delivery |
| `validate_integration.py` | End-to-end + privacy validation |
| `remediate_content_pii.py` | Redact residual @handles in stored text |
| `migrate_sqlite_chroma_to_postgres.py` | One-time migration from legacy SQLite + Chroma |

## Project Structure

```
├── collectors/       # Data collection
├── processing/       # Clean, anonymize, normalize
├── analysis/         # NLP, RAG, retrieval
├── api/              # FastAPI backend
├── dashboard/        # Streamlit UI
├── validation/       # Pulse validators + privacy audit
├── delivery/         # Weekly pulse runner
├── models/           # SQLAlchemy ORM schema
├── utils/            # Config, logging, exceptions
├── scripts/          # init_db, pipeline, validation
├── tests/            # pytest tests
├── data/             # Local data (gitignored)
└── docs.md/          # Project documentation
```

## Privacy

- Usernames replaced with `user_<hash>` before processed storage
- Email, phone, and credential patterns redacted or blocked
- Phase 9 privacy audit: `validation/privacy_audit.py` + `scripts/validate_integration.py --offline`
- See [Privacy Checklist](docs.md/phase-0/Privacy%20Checklist.md)

## Data Sources

Public feedback from Google Play Store, Apple App Store, Reddit (optional), and Spotify Community forum — discovery-related content only.

## License

Graduation project — academic use.
