# Demo Script — Spotify Review Discovery Engine

Use this walkthrough for mentor review, viva, or stakeholder demo. Total time: **10–15 minutes**.

## Before You Start

1. Activate the virtual environment.
2. Ensure data exists (`data/reviews.db` with processed reviews).
3. Run Phase 9 validation:

```powershell
.venv\Scripts\python scripts\validate_integration.py
```

4. Start two terminals:

```powershell
# Terminal 1 — API
.venv\Scripts\python -m uvicorn api.main:app --reload

# Terminal 2 — Dashboard
.venv\Scripts\python -m streamlit run dashboard/app.py
```

Open **http://localhost:8501** (dashboard) and **http://localhost:8000/docs** (API docs).

---

## Demo Flow

### 1. Problem framing (1 min)

Explain the six research questions the engine must answer from public Spotify discovery feedback:

1. Why do users struggle to discover new music?
2. What are the most common recommendation frustrations?
3. What listening behaviors are users trying to achieve?
4. What causes repetitive listening loops?
5. Which segments experience discovery differently?
6. What unmet needs appear consistently?

### 2. Overview tab (3 min)

- Show the **shared filter bar** (source + date range) and active filter summary.
- Walk through metric cards: total reviews, complaints, themes, average rating.
- Open **Research questions** — six cards with criticality stars and “Based on N reviews”.
- Expand one card’s **supporting evidence** to show review excerpts and `review_id` citations.
- Point to the **Latest Weekly Pulse** card and Doc link (if generated).

### 3. Themes & Chat tab (3 min)

- Show top themes with complaint-based labels and evidence badges.
- Expand a theme’s evidence quotes.
- Ask a starter question in chat, e.g. *“Why do users struggle to discover new music?”*
- Highlight: answer cites reviews, shows criticality, and refuses when evidence is insufficient.

### 4. Segments & Unmet Needs (2 min)

- **Segments:** directional clusters with review counts and representative quotes.
- **Unmet Needs:** ranked pain points with evidence strength (Low / Medium / High).

### 5. Review Discovery tab (1 min)

- Search for a keyword (e.g. `repetitive recommendations`).
- Show raw results with sentiment badges and `review_id` for traceability.

### 6. Privacy & validation (2 min)

- Mention usernames are replaced with `user_<hash>` before storage.
- Run offline privacy audit:

```powershell
.venv\Scripts\python scripts/validate_integration.py --offline
```

- Optional: redact residual forum @mentions in stored text:

```powershell
.venv\Scripts\python scripts/remediate_content_pii.py --dry-run
.venv\Scripts\python scripts/remediate_content_pii.py
```

### 7. API proof (optional, 2 min)

In Swagger (`/docs`), call:

- `GET /api/questions`
- `GET /api/search?q=shuffle`
- `GET /api/chat?q=What causes repetitive listening loops?`

---

## Full Pipeline (if rebuilding from scratch)

```powershell
python scripts/init_db.py
python scripts/run_collection.py
python scripts/run_processing.py
python scripts/run_analysis.py
python scripts/run_pulse.py --dry-run
.venv\Scripts\python -m pytest tests/ -v
.venv\Scripts\python scripts/validate_integration.py
```

---

## Troubleshooting

| Issue | Fix |
|---|---|
| Dashboard shows “Backend offline” | Start uvicorn in Terminal 1 |
| Empty charts / zero reviews | Run collection → processing → analysis |
| Chat refuses every question | Broaden date filter or re-run analysis to rebuild Chroma index |
| Weekly pulse missing | Run `python scripts/run_pulse.py --dry-run` |
