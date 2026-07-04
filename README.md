# Review Discovery Engine

AI-powered platform that aggregates publicly available user feedback about Spotify's music discovery experience, analyzes it with NLP, and surfaces structured, evidence-backed insights for product research.

## Project Status

| Phase | Status |
|---|---|
| Phase 0 — Research & Planning | Complete |
| Phase 1 — Project Setup & Foundation | Complete |
| Phase 2 — Data Collection | Complete |
| Phase 3 — Data Processing | Complete |
| Phase 4 — NLP Analysis | Complete |
| Phase 5 — Backend API | Complete |
| Phase 6 — Dashboard | Complete |
| Phase 7 — Report & Docs | Pending |
| Phase 8 — Testing & Delivery | Pending |

## Documentation

- [Problem Statement](docs.md/Problem%20Statement.md)
- [System Architecture](System%20Architecture.md)
- [Phase-Wise Plan](Phase%20wise%20architecture.md)
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
# Install all required packages
pip install -r requirements.txt
```

### Step 3: Initialize the Database

```bash
# Create database tables and schema
python scripts/init_db.py
```

Expected output: `Database initialized at sqlite:///data/reviews.db`

### Step 4: Start the API Backend (Terminal 1)

```bash
# Run the FastAPI server (use the venv Python on Windows)
.venv\Scripts\python -m uvicorn api.main:app --reload
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

- **API Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

### Step 5: Start the Dashboard (Terminal 2)

```bash
# Launch the Streamlit dashboard in a new terminal (keep API running)
# Recommended: use the virtual environment's Python directly
.venv\Scripts\python -m streamlit run dashboard/app.py
```

If PowerShell says `streamlit` is not recognized, that means Streamlit is installed inside the project's virtual environment and is not available as a global command. Using `.venv\Scripts\python -m streamlit run dashboard/app.py` works reliably.

You should see:
```
You can now view your Streamlit app in your browser.
Local URL: http://localhost:8501
```

### Step 6: Open the Dashboard

Visit **http://localhost:8501** in your browser to access the dashboard.

---

## Running Tests

```bash
# Run all unit tests
pytest tests/ -v
```

---

## Optional: Data Pipeline Scripts

Once data is collected and processed, use these to regenerate analysis:

```bash
# Collect data from sources (Phase 2)
python scripts/run_collection.py

# Process and clean data (Phase 3)
python scripts/run_processing.py

# Run NLP analysis (Phase 4)
python scripts/run_analysis.py
```

## Project Structure

```
├── collectors/       # Phase 2 — data collection
├── processing/       # Phase 3 — clean, anonymize, normalize
├── analysis/         # Phase 4 — NLP pipeline
├── api/              # Phase 5 — FastAPI backend
├── dashboard/        # Phase 6 — Streamlit UI
├── reports/          # Phase 7 — insight report export
├── models/           # SQLAlchemy ORM schema
├── utils/            # Config, logging, exceptions
├── scripts/          # Utility scripts (init_db, etc.)
├── tests/            # pytest tests
├── data/             # Local data (gitignored)
└── docs.md/          # Project documentation
```

## Data Collection (Phase 2)

Run collectors to gather public Spotify discovery feedback:

```bash
python scripts/run_collection.py
```

Collect from specific sources only:

```bash
python scripts/run_collection.py --sources play_store,app_store,spotify_community
```

### Sources & Methods

| Source | Tool | What it collects |
|---|---|---|
| Google Play Store | `google-play-scraper` | Spotify app reviews (`com.spotify.music`) |
| Apple App Store | iTunes RSS API | Spotify app reviews (ID `324684580`) |
| Spotify Community | Khoros LiQL API | Forum posts about discovery & recommendations |
| Reddit | PRAW | Posts/comments from r/spotify (requires `.env` credentials) |

### Filtering

Only reviews/posts about **music discovery** are kept (keywords like *discover weekly*, *algorithm*, *recommendations*, *playlist*, etc.).

### Output

- Records saved to `raw_reviews` table in SQLite
- Cleaned reviews, themes, insights, quotes, and pulse runs stored in SQLite
- Embeddings and semantic search index stored in local Chroma (`data/chroma/`)
- JSON backups in `data/raw/`
- Summary report in `data/collection_report.md`

## Data Processing (Phase 3)

Clean and anonymize raw reviews before NLP analysis:

```bash
python scripts/run_processing.py
```

### What the pipeline does

1. **Validates** — removes empty, too-short, or invalid records
2. **Cleans text** — fixes encoding, extra spaces, HTML entities
3. **Removes personal info** — redacts emails and phone numbers
4. **Anonymizes usernames** — replaces real names with `user_abc12345`
5. **Removes duplicates** — same text appearing across sources
6. **Saves** clean records to the `reviews` table

Report saved at: `data/processing_report.md`

## NLP Analysis (Phase 4)

Run AI analysis on cleaned reviews:

```bash
python scripts/run_analysis.py
```

Regenerate themes and insights:

```bash
python scripts/run_analysis.py --force-themes
```

### What the analysis does

1. **Sentiment** — labels each review as positive, negative, or neutral
2. **Embeddings** — converts text to numbers the computer can compare (for search)
3. **Theme clustering** — groups similar reviews together (BERTopic)
4. **Insights** — writes plain-English findings with evidence quotes
5. **Search index** — saves embeddings in local Chroma for the dashboard search box and retrieval

Report saved at: `data/analysis_report.md`

## Data Sources

Public feedback from:

- Google Play Store (`com.spotify.music`)
- Apple App Store (Spotify app)
- Reddit (r/spotify, r/truespotify)
- Spotify Community forum (Discourse)

## License

Graduation project — academic use.
