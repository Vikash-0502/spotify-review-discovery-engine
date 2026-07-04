# Learning Log

A running log of architecture and scope updates for quick review.

---

## How to Run the Project Locally

### Prerequisites

- Python 3.11 or higher
- pip (Python package manager)
- Git (if cloning from repository)

### Complete Setup (First Time)

**Terminal 1 — Set Up Environment**

```bash
# Navigate to project
cd "Graduation Project"

# Create virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\activate          # Windows
# source .venv/bin/activate    # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Initialize database
python scripts/init_db.py
```

**Terminal 2 — Start API Backend**

```bash
uvicorn api.main:app --reload
```

When you see `Uvicorn running on http://0.0.0.0:8000`, the API is ready.

**Terminal 3 — Start Dashboard**

```bash
streamlit run dashboard/app.py
```

When you see `You can now view your Streamlit app in your browser`, open the URL.

### Access Points

| Service | URL | Purpose |
|---------|-----|----------|
| Dashboard | http://localhost:8501 | View insights, search reviews, explore themes |
| API Docs | http://localhost:8000/docs | Interactive API documentation (Swagger UI) |
| API Health | http://localhost:8000/health | Check if backend is running |
| ReDoc | http://localhost:8000/redoc | Alternative API docs format |

### Quick Restart (After Initial Setup)

Once environment is set up, you only need:

```bash
# Terminal 1 — Activate & start API
.venv\Scripts\activate
uvicorn api.main:app --reload

# Terminal 2 — Start dashboard (in new terminal)
streamlit run dashboard/app.py
```

### Troubleshooting

**API not starting?**

```bash
# Reinitialize database
python scripts/init_db.py

# Check if port 8000 is in use
netstat -ano | findstr :8000          # Windows
lsof -i :8000                          # macOS/Linux
```

**Dashboard can't connect to API?**

- Make sure API is running in another terminal
- Check that http://localhost:8000/health returns `{"status":"ok", ...}`
- Ensure you're using localhost (not 127.0.0.1) to avoid CORS issues

---

## 2026-07-04 — Storage Update (Chroma for Embeddings)

**In simple terms:** We changed how search data is stored. The project now uses **Chroma** as the vector database for embeddings and semantic search, while **SQLite** still stores the normal structured data like reviews, themes, sentiment, segments, and quotes.

### What Changed

- **Chroma** now stores review embeddings
- Semantic search now reads from **Chroma** instead of reading embedding blobs from SQLite
- **SQLite** is still used for:
  - raw reviews
  - cleaned reviews
  - review/theme links
  - theme names
  - sentiment labels
  - segment labels
  - insights and quotes
  - weekly pulse records

### Why This Is Better

- Chroma is built for **vector search**
- It makes the embedding/search part match the intended architecture better
- SQLite remains good for the structured relational data
- This gives us a cleaner **hybrid storage model** instead of forcing one database to do everything

### Result

- Existing reviews were re-indexed into Chroma
- The weekly pulse still works
- Tests still pass after the change

---

## 2026-07-04 — Dashboard Update (Weekly Pulse UI + Top Navigation)

**In simple terms:** We connected the dashboard to the new weekly pulse API and cleaned up the top part of the screen to look closer to the reference design. The important tabs are still there, but now they sit in a top navigation bar instead of feeling hidden in a side menu.

### What Was Changed

- Added dashboard support for `GET /api/weekly-pulse/latest`
- The **Overview** tab now shows the latest weekly pulse summary
- If a Google Doc link exists, the dashboard shows it; if not, it shows the saved local preview path
- Moved the main page navigation to a **top navigation bar**
- Kept the main sections: **Overview**, **Themes & Chat**, **Segments**, **Unmet Needs**, **Review Discovery**
- Removed the extra top text like:
  - `NL. AI review engine`
  - `Live feed from Spotify Play Store · Google Play · ...`
- Kept the cleaner header with pipeline status and refresh action

### Files Updated

| File | Update |
|---|---|
| `dashboard/app.py` | Added weekly pulse fetch + UI card, moved navigation to top bar, simplified header |
| `api/routes/analytics.py` | Already exposes the latest weekly pulse endpoint used by the dashboard |

### Verification

- Dashboard file compiles correctly
- API tests still pass after the UI/API integration

---

## 2026-07-04 — Architecture Update (Weekly Pulse + Validation Layer)

**In simple terms:** We upgraded the *design* of the system. It still has the same goal and the same dashboard + chatbot, but now the design also includes writing a short weekly summary into a Google Doc automatically, and a strict rule-based "safety checker" that reviews the AI's output before anything is shown or saved.

### What Changed (and why)

| Change | What it means in plain words |
|---|---|
| **Stratified sampling** | Instead of sending thousands of reviews to the AI, we pick a smart, balanced sample (more of the angry ones, spread evenly across weeks). Faster, cheaper, and repeatable. |
| **Two-stage Groq pipeline** | The AI now works in two clear steps: Step A finds the themes, Step B writes the readable summary/cards. Splitting the job makes each step sharper and easier to fix. |
| **Validation layer** | A rule-based (not AI) checker that verifies theme counts, word limits, that every quote is real (traces back to an actual review), and that there's no personal info — **before** anything is published or saved. |
| **Weekly pulse to Google Docs (via MCP)** | The system writes a short weekly report (top 3 themes, 3 quotes, 3 action ideas, ≤250 words) straight into a Google Doc using an MCP server — no hand-written Google login code. |
| **No Gmail / email** | We deliberately skipped emailing the report. It lives in Google Docs and is linked from the dashboard. |

### What Stayed the Same (scope preserved)

- The **Streamlit dashboard** (5 tabs) and the **RAG chatbot** are still core.
- **Chroma vector store** + **local embeddings** (zero Groq cost) unchanged.
- **Privacy rules** unchanged — no usernames, emails, or device IDs anywhere.
- **Max 5 themes** and **≤250-word** narrative cards unchanged.
- **`Problem Statement.md` was not edited** — its scope stays the source of truth.

### Files Updated

| File | Update |
|---|---|
| `System Architecture.md` | Fully rewritten into a clearer structure (purpose, quality attributes, context diagram, pipeline, logical components, trust boundaries, data contracts, sequence diagrams, failure/retry, deployment) — now including sampling, two-stage Groq, the validation layer, and Google Docs MCP delivery |
| `Phase wise architecture.md` | Re-aligned to the new architecture. Added a new **Phase 6 — Validation & Weekly Pulse (Docs MCP)** and renumbered the rest (now Phases 0–9) |

### New Phase Order (0–9)

`0 Research → 1 Foundation → 2 Ingestion → 3 Processing → 4 Embedding & Themes (sampling + Stage A/B Groq) → 5 Segments & Needs → 6 Validation & Weekly Pulse (Docs MCP) → 7 API & Search → 8 Dashboard → 9 Integration & Delivery`

### Note on Already-Built Phases

Phases 2–6 were previously built with an older approach. The updated architecture describes the intended target design (Groq two-stage + validation + Docs MCP pulse). Re-aligning existing code to it — especially the new **Phase 6 validation + weekly pulse** — is future work, now captured in the phase plan.

---

## 2026-06-27 — Phase 6 Complete (Dashboard Redesign & Research Questions)

**In simple terms:** We updated and redesigned our dashboard to make it much more powerful and aligned with our main research goals!

### What Was Done

1. **Source Filters**: You can now select a specific platform (like Google Play, App Store, or Spotify Community) from the sidebar. When you select a source, the entire dashboard automatically updates to show only reviews and insights from that specific source.
2. **🔬 Research Questions Analysis Panel**: The centerpiece of the dashboard now answers 6 specific research questions (e.g. why users struggle to discover music, or common recommendation frustrations).
   - Each question is rated on a **1 to 5 star rating system** (★★★★★) based on how crucial/severe the issue is in the reviews.
   - The dashboard automatically sorts the questions so the most crucial issues appear at the top.
   - Under each question, you get an AI-generated summary, a sentiment breakdown, a list of related themes, and real user quotes as evidence.
3. **🏷️ Theme Friction Segmentation**: All discovered themes are now segmented into clear categories so you can instantly spot high friction areas:
   - `🔴 High Friction` (when more than 60% of feedback is negative)
   - `🟠 Moderate Friction` (when 40-60% of feedback is negative)
   - `🔥 Trending Now` (for issues that appeared very recently in the last 30 days)
   - `🟢 Positive Signal` (when feedback is mostly positive)

### How to Run It

1. Start the API server:
   ```bash
   uvicorn api.main:app --reload
   ```

2. Run the dashboard:
   ```bash
   streamlit run dashboard/app.py
   ```

---

## 2026-06-27 — Phase 6 Initial Implementation (Dashboard UI)

**In simple terms:** We finished building the first version of the dashboard! It is a web page with charts and a search box. It connects directly to our API backend instead of the database. This means it can fetch summary numbers, user sentiment, main complaints, and real quotes, and search for reviews instantly over the network. If the API backend is turned off, the dashboard will warn you and show you how to turn it on.


### What Was Built

| Feature | What it does |
|---|---|
| **API Health Check** | Automatically checks if the FastAPI backend is running. If not, it shows a friendly banner on how to start it. |
| **Overview Cards** | Displays key numbers: total reviews, number of themes, number of platforms, and % negative feedback. |
| **Sentiment & Platforms Charts** | Shows visual graphs of positive/negative/neutral split and where reviews came from. |
| **Top Themes & Pain Points** | Displays lists of clustered user feedback and ranked problems. |
| **Representative Quotes** | Lists real, verbatim user comments for researchers to read. |
| **Smart Search Results** | Queries the search API and shows matching reviews with their date, platform, and sentiment badge. |

### How to Run It

1. Start the API server first:
   ```bash
   uvicorn api.main:app --reload
   ```

2. Then, run the dashboard:
   ```bash
   streamlit run dashboard/app.py
   ```

---

## 2026-06-27 — Phase 5 Complete (Backend API & Search)

**In simple terms:** We built the "bridge" (API) that allows the dashboard to ask questions and get insights from the database. We also added a smart search feature so you can find specific reviews by typing a keyword or a concept.

### What Was Built

| Feature | What it does |
|---|---|
| `/api/stats` | Gives a quick overview of how many reviews we have and where they came from. |
| `/api/themes` | Returns the top recurring themes found in the feedback. |
| `/api/sentiment` | Shows the split between positive, negative, and neutral reviews. |
| `/api/pain-points` | Lists the most critical problems users are facing, ranked by priority. |
| `/api/quotes` | Fetches real user quotes to back up the themes. |
| `/api/search` | A smart search that looks for both exact words and similar meanings (using AI embeddings). |

### Key Decisions

- We used **FastAPI** to build the endpoints because it's fast and auto-generates documentation.
- We added **CORS** support so the Streamlit dashboard can talk to the API directly.
- All endpoints support **date filtering**, allowing the dashboard to slice data by specific time periods.

### How to Run It

```bash
uvicorn api.main:app --reload
```

Then visit `http://localhost:8000/docs` to test the API directly!

### Next Step

**Phase 6 — Dashboard UI** (building the visual interface with charts and the search box)

---
## 2026-06-27 — Phase 4 Complete (NLP / AI Analysis)

**In simple terms:** We used AI to read all 2,275 clean reviews, figure out if people are happy or upset, group similar complaints together into themes, and write summary insights with real user quotes as proof.

### What Happens Step by Step

1. **Clean the text** — remove junk so the AI reads useful words only
2. **Sentiment** — each review gets a label: happy, unhappy, or neutral
3. **Embeddings** — each review becomes a list of numbers so similar reviews can be found later (for search in Phase 5)
4. **Themes** — BERTopic groups reviews that talk about the same thing (e.g. shuffle, ads, AI music)
5. **Insights & quotes** — the system writes short summaries and picks real user quotes as evidence

### What Was Built

| File | What it does |
|---|---|
| `analysis/preprocessing.py` | Cleans text and filters out spam/noise before AI runs |
| `analysis/sentiment.py` | Labels each review as positive, negative, or neutral |
| `analysis/embeddings.py` | Converts review text into searchable number vectors |
| `analysis/themes.py` | Groups similar reviews into themes using BERTopic |
| `analysis/insights.py` | Writes summary findings and picks the best user quotes |
| `analysis/pipeline.py` | Runs all analysis steps in order |
| `analysis/report.py` | Creates the summary report after analysis |
| `scripts/run_analysis.py` | One command to run everything |

### AI Models Used

| Task | Model |
|---|---|
| Sentiment | `cardiffnlp/twitter-roberta-base-sentiment-latest` |
| Embeddings & themes | `all-MiniLM-L6-v2` + BERTopic |

### Results

| Output | Count |
|---|---|
| Reviews analyzed | 2,275 |
| Themes discovered | 16 |
| Insights generated | 50 |
| Representative quotes | 48 |
| Search embeddings saved | 2,275 |

### Sentiment Breakdown

| Feeling | Reviews | Share |
|---|---|---|
| Negative | 1,177 | 52% |
| Positive | 734 | 32% |
| Neutral | 364 | 16% |

### Example Themes Found

- **Shuffle problems** — 273 reviews (users complain about shuffle playing wrong songs)
- **Ads frustration** — 216+ reviews (ads interrupting music experience)
- **Music quality** — 143 reviews (positive feedback about the music itself)
- **AI-generated music concerns** — 37 reviews (worries about AI content)

### How to Run It

```bash
python scripts/run_analysis.py
```

Report saved at: `data/analysis_report.md`

### Exit Criteria — All Met

- [x] Every review has a sentiment label
- [x] Themes with name, count, sentiment, and date range
- [x] Insights linked to quotes and review counts
- [x] Search index ready (embeddings saved)
- [x] All insights backed by real user quotes

### Next Step

**Phase 5 — Backend API & Search** (build endpoints so the dashboard can show themes, search reviews, and filter by date)

---

## 2026-06-27 — Phase 3 Complete (Data Processing)

**In simple terms:** We took the raw reviews we collected and cleaned them up — removed junk, hid personal info, replaced real usernames with anonymous IDs, and saved the clean version ready for AI analysis.

### What Was Built

| File | What it does |
|---|---|
| `processing/validation.py` | Rejects empty, too-short, or bad-date records |
| `processing/pii_scanner.py` | Finds and removes emails and phone numbers from text |
| `processing/anonymizer.py` | Turns real usernames into anonymous IDs like `user_abc12345` |
| `processing/normalizer.py` | Cleans up messy text (extra spaces, HTML codes, dates) |
| `processing/dedup.py` | Removes duplicate reviews that say the same thing |
| `processing/pipeline.py` | Runs all cleaning steps in order |
| `processing/report.py` | Creates a summary report after processing |
| `scripts/run_processing.py` | One command to run the full pipeline |

### What Happened to the Data

| Step | Count |
|---|---|
| Raw records checked | 2,317 |
| Clean records saved | **2,275** |
| Dropped (bad/irrelevant) | 42 |
| Duplicates removed | 4 |
| Personal info redacted | 12 |

### Clean Data by Source

| Source | Records |
|---|---|
| Google Play Store | 1,660 |
| Spotify Community | 541 |
| Apple App Store | 74 |

### Privacy Checks

- [x] No emails or phone numbers left in processed text
- [x] All usernames replaced with anonymous IDs
- [x] Real names never stored in the `reviews` table

### How to Run It

```bash
python scripts/run_processing.py
```

Report saved at: `data/processing_report.md`

### Next Step

**Phase 4 — NLP Analysis** (sentiment scoring, theme clustering, insight generation)

---

## 2026-06-27 — Phase 2 Complete (Data Collection)

**In simple terms:** We built robots that go out to the internet, grab public Spotify reviews and forum posts, filter them for music discovery topics, and save them in our database.

### What Was Built

| File | What it does |
|---|---|
| `collectors/keywords.py` | Checks if a review is about music discovery (e.g. "discover weekly", "algorithm") |
| `collectors/play_store.py` | Grabs Google Play Store reviews for the Spotify app |
| `collectors/app_store.py` | Grabs Apple App Store reviews via iTunes RSS |
| `collectors/reddit_collector.py` | Grabs Reddit posts/comments (needs API keys in `.env`) |
| `collectors/spotify_community.py` | Grabs Spotify Community forum posts |
| `collectors/base.py` | Saves records to the database, skips duplicates |
| `collectors/report.py` | Creates a summary report after collection |
| `scripts/run_collection.py` | One command to run all collectors |

### How Much Data We Collected

| Source | Records |
|---|---|
| Google Play Store | 1,540 |
| Spotify Community | 582 |
| Apple App Store | 74 |
| **Total** | **2,196** |

Reddit was skipped because API keys are not set in `.env` yet. You can add them later to collect more.

### How to Run It Again

```bash
python scripts/run_collection.py
```

Report saved at: `data/collection_report.md`

### Exit Criteria — All Met

- [x] 2,000+ records collected from 3 sources
- [x] Each record has platform, text, date, and source link
- [x] Only public data collected
- [x] Collection steps documented in README

### Next Step

**Phase 3 — Data Processing** (clean text, remove personal info, anonymize usernames)

---

## 2026-06-27 — Phase 1 Complete (Project Setup & Foundation)

**Source:** Phase 1 implementation per `Phase wise architecture.md`.

### What Was Done

| Task | Output |
|---|---|
| 1.1 Project structure | `collectors/`, `processing/`, `analysis/`, `api/`, `dashboard/`, `reports/`, `models/`, `utils/`, `scripts/`, `tests/`, `data/` |
| 1.2 Dependencies | `requirements.txt` + `.venv` virtual environment |
| 1.3 Environment config | `.env.example` with Reddit, DB, NLP, and API variables |
| 1.4 Database schema | `models/schema.py` (ORM) + `models/schema.sql` (reference) + `scripts/init_db.py` |
| 1.5 ORM models | 7 tables: `raw_reviews`, `reviews`, `review_embeddings`, `themes`, `review_themes`, `insights`, `quotes` |
| 1.6 Shared utilities | `utils/config.py`, `utils/logging.py`, `utils/exceptions.py` |
| 1.7 README | Setup instructions, project structure, verify commands |
| Git | Repository initialized; `.gitignore` excludes data, secrets, and venv |

### Database Tables Created

| Table | Purpose |
|---|---|
| `raw_reviews` | Unmodified collector output |
| `reviews` | Cleaned, anonymized, normalized records |
| `review_embeddings` | Search index vectors |
| `themes` | Clustered feedback groups |
| `review_themes` | Review ↔ theme join |
| `insights` | Structured product discovery outputs |
| `quotes` | Representative verbatim excerpts |

### Verification

```bash
python scripts/init_db.py   # ✅ tables created
pytest tests/ -v            # ✅ 3/3 passed
```

### Exit Criteria — All Met

- [x] Project runs locally without errors
- [x] Database connects and tables are created
- [x] Base models match `System Architecture.md` conceptual model

### Next Step

**Phase 2 — Data Collection** (Play Store, App Store, Reddit, Spotify Community collectors)

---

## 2026-06-27 — Phase 0 Complete (Research & Planning)

**Source:** Phase 0 implementation per `Phase wise architecture.md`.

### What Was Done

| Task | Deliverable |
|---|---|
| 0.1 Research notes | `docs.md/phase-0/Research Notes.md` — 6 pain point themes, success metrics, references |
| 0.2 Source feasibility | `docs.md/phase-0/Data Source Feasibility Matrix.md` — all 4 primary sources confirmed viable |
| 0.3 Collection strategy | Rate limits, tools, and ToS notes per platform (same doc) |
| 0.4 Keyword targets | `docs.md/phase-0/Keyword and Source Targets.md` — keywords, subreddits, forum boards |
| 0.5 NLP selection | `docs.md/phase-0/NLP Tool Selection.md` — BERTopic + MiniLM + RoBERTa sentiment |
| 0.6 Data model | `docs.md/phase-0/Data Model Draft.md` — 7 tables, API response shapes |
| 0.7 Privacy rules | `docs.md/phase-0/Privacy Checklist.md` — PII stripping, anonymization, stage gates |
| 0.8 Architecture | Already complete — `System Architecture.md`, `Phase wise architecture.md` |
| Tech stack | `docs.md/phase-0/Tech Stack Selection.md` — Python, FastAPI, Streamlit, SQLite |
| Summary | `docs.md/phase-0/Phase 0 Summary.md` — exit criteria checklist |

### Key Decisions

- **Data sources:** Google Play (`com.spotify.music`), App Store (`324684580`), Reddit (PRAW), Spotify Community (Discourse API)
- **Social media:** Optional — deprioritized due to API restrictions
- **NLP stack:** Local open-source only — `all-MiniLM-L6-v2` embeddings, BERTopic clustering, `twitter-roberta` sentiment
- **Search:** Hybrid semantic + BM25, reusing Phase 4 embeddings
- **Stack:** Python 3.11+, FastAPI, Streamlit, SQLite, SQLAlchemy

### Exit Criteria — All Met

- [x] Primary data sources confirmed publicly accessible
- [x] NLP approach chosen with rationale
- [x] Tech stack and repo structure defined
- [x] Architecture aligned with problem statement

### Next Step

**Phase 1 — Project Setup & Foundation** (repo structure, DB schema, base models, `.env.example`)

---

## 2026-06-27 — Search & Date Filter Enhancements

**Source:** Scope refinement on top of the original Review Discovery Engine architecture (see `System Architecture.md`).

### What Changed

| Area | Update |
|---|---|
| **Cause Search Box** | Added a dashboard search box where users enter a cause, pain point, theme, or keyword and receive relevant reviews and Reddit discussions |
| **Search Service** | New API component that performs semantic (embedding-based) and keyword search over indexed review content |
| **Search Index** | New storage layer reusing NLP embeddings plus keyword indexes for fast on-demand lookup — no re-run of the full NLP pipeline at search time |
| **Date-Wise Filters** | Dashboard-wide date filtering with *Latest first* default sort, custom date range, and presets (*Last 7 days*, *Last 30 days*, *Last 3 months*, *All time*) |
| **Search Results Panel** | New dashboard panel showing ranked matches with platform source, posted date, sentiment, and excerpt |
| **Search & Discovery Flow** | New sequence diagram documenting query → search API → index → filtered results |

### What Stayed the Same

- Original four-stage pipeline: **Ingestion → Processing → Analysis → Presentation**
- Data sources, privacy constraints, and research-only scope (no automated product recommendations)
- NLP theme clustering, insight generation, and evidence traceability requirements
- Deliverables: README, Dashboard, Insight Report

### Files Updated

- `System Architecture.md` — diagrams, component table, dashboard section, and new Search & Discovery Flow
- `docs.md/Learning Log.md` — this entry

### Key Design Notes

1. Search is a **presentation-layer extension** — it reads from already-processed data rather than changing ingestion or analysis scope.
2. Embeddings produced during the NLP pipeline are **reused** for semantic search, avoiding duplicate AI work.
3. Date filters apply **consistently** across all dashboard panels and search results via shared API query parameters.
