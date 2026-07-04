# Implementation Plan

## AI-Powered Review Discovery Engine — Spotify

This is the **phased delivery detail** for the project. It turns the phases in `Phase wise architecture.md` into concrete, buildable steps: what modules to create, what each step depends on, how to run it, and how to know it is done.

- **Scope source of truth:** `docs.md/Problem Statement.md` (unchanged)
- **Architecture source of truth:** `System Architecture.md`
- **Phase structure:** `Phase wise architecture.md` (Phases 0–9)

> **Delivery model:** interactive **Streamlit dashboard + RAG chatbot**, plus a **weekly pulse written to Google Docs via MCP**. **No Gmail / email delivery.**

---

## How to Read This Plan

Each phase below has:

- **Goal** — one line on the outcome.
- **Depends on** — which phase(s) must exist first.
- **Build steps** — ordered, concrete tasks with target files/modules.
- **Run** — commands to execute or verify the phase.
- **Done when** — the exit criteria to check before moving on.
- **Status** — current state in this repo.

Status legend: ✅ Built · 🟡 Partial / older approach · ⬜ Not started

---

## Status Summary

| Phase | Name | Status | Notes |
|---|---|---|---|
| 0 | Research & Planning | ✅ Built | Docs in `docs.md/phase-0/` |
| 1 | Foundation | ✅ Built | Repo, schema, utils, `init_db` |
| 2 | Ingestion | 🟡 Partial | Multi-source collectors exist; target is public export ingestion |
| 3 | Processing | ✅ Built | Validation, PII, normalize, dedup |
| 4 | Embedding & Themes | 🟡 Partial | Chroma storage for embeddings is now implemented; Stage A/B Groq theme flow is still the target |
| 5 | Segments & Needs | 🟡 Partial | Some analysis exists; segment/needs need alignment |
| 6 | Validation & Weekly Pulse (Docs MCP) | ✅ Built | Validator + quota-safe pulse runner + dry-run / MCP command bridge |
| 7 | API & Search | ✅ Built | FastAPI endpoints, hybrid Chroma search, grounded `/api/chat` RAG endpoint |
| 8 | Dashboard | ✅ Built | Five tabs, shared filters, research-question cards, evidence badges, accessible palette |
| 9 | Integration & Delivery | ✅ Built | End-to-end validation script, privacy audit, demo script, docs |

> The updated architecture uses a **hybrid storage model**: **Chroma** stores embeddings and powers semantic retrieval, while **SQLite** stores structured records like reviews, sentiment, themes, segments, quotes, and pulse runs. Phases marked 🟡 still need partial re-alignment to the full target design.

---

## Phase 0 — Research & Planning

**Goal:** Confirm requirements, scope, and technical approach before building.
**Depends on:** —

### Build steps

1. Capture the six research questions and acceptance criteria.
2. Confirm public export ingestion only (no ToS-violating scraping).
3. Choose tools: local embeddings, Chroma vector store, Groq for generation.
4. Define theme / segment / unmet-needs outputs and privacy rules.

### Run

- Review docs in `docs.md/phase-0/`.

### Done when

- Problem statement, tool choices, privacy rules, and architecture are documented and aligned.

**Status:** ✅ Built (`docs.md/phase-0/`)

---

## Phase 1 — Foundation

**Goal:** Establish repo structure, environment, schema, and utilities.
**Depends on:** Phase 0

### Build steps

1. Create folders: `collectors/ processing/ analysis/ api/ dashboard/ models/ utils/ scripts/ tests/ data/`.
2. Add `utils/config.py`, `utils/logging.py`, `utils/exceptions.py`.
3. Define ORM schema in `models/schema.py` (+ reference `models/schema.sql`).
4. Add `requirements.txt`, `.env.example`, `.gitignore`, `README.md`.
5. Add `scripts/init_db.py` to create tables.

### Run

```bash
python scripts/init_db.py
pytest tests/ -v
```

### Done when

- Project boots locally, DB connects, tables are created.

**Status:** ✅ Built

---

## Phase 2 — Ingestion

**Goal:** Ingest 8–12 weeks of public Spotify Play Store reviews (App Store optional) from public export.
**Depends on:** Phase 1

### Build steps

1. Build an export parser that reads public review export files.
2. Map platform columns to shared fields: `review_id, platform, review_date, rating, title, body, app_version, thumbs_up`.
3. Tolerate header variants, missing optional fields, and encoding issues.
4. Apply the configurable 8–12 week lookback window (consistent timezone handling).
5. Persist to the raw store (`raw_reviews`).
6. Document required export format and steps in `README.md`.

### Run

```bash
python scripts/run_collection.py      # existing runner (multi-source today)
```

### Done when

- Only public export data is ingested, with required metadata fields and configurable date range.

**Status:** 🟡 Partial — collectors exist (`collectors/`); align to **export-based** ingestion per the updated architecture. Existing report: `data/collection_report.md`.

---

## Phase 3 — Processing

**Goal:** Clean and normalize raw reviews into a privacy-safe, English-only corpus.
**Depends on:** Phase 2

### Build steps

1. `processing/normalizer.py` — strip HTML, whitespace, repeated characters; normalize dates.
2. `processing/pii_scanner.py` + `processing/anonymizer.py` — remove emails, phones, device IDs; drop reviewer handles.
3. `processing/validation.py` — drop emoji-only, sub-threshold, and bad-date records.
4. `processing/dedup.py` — collapse near-duplicates (same body + close timestamp + platform).
5. English-only filter; flag non-English for future expansion.
6. `processing/pipeline.py` + `scripts/run_processing.py`; write `data/processing_report.md`.

### Run

```bash
python scripts/run_processing.py
```

### Done when

- No PII in processed records; reviews normalized, deduplicated, English-only; ready for embedding.

**Status:** ✅ Built (`processing/`, `data/processing_report.md`)

---

## Phase 4 — Embedding & Themes

**Goal:** Local embeddings in Chroma, stratified sampling, and a two-stage Groq pipeline to produce ≤5 evidence-cited theme cards.
**Depends on:** Phase 3
**Maps to:** System Architecture §5.2, §5.3

### Build steps

1. `analysis/embeddings.py` — embed with `sentence-transformers/all-MiniLM-L6-v2` (local, zero quota).
2. Persist vectors + metadata (`review_id, rating, review_date, platform`) to a **file-backed Chroma** store; this index serves both clustering and RAG retrieval.
3. Keep **SQLite** as the system of record for raw reviews, cleaned reviews, cluster links, theme names, sentiment scores, segment labels, quotes, and pulse metadata.
4. `analysis/sampling.py` — stratified sample by **rating tier (≤2★ / 3★ / 4–5★) × ISO week**, oversample negatives, cap per week, record `seed` + caps in run metadata.
5. `analysis/themes.py`:
   - **Stage A (Groq):** send the sample, request **≤5 themes** with label, one-line description, and supporting `review_id`s.
   - **Stage B (Groq):** generate narrative cards (**≤250 words**) with representative quotes cited by `review_id`.
6. Extract representative quotes; detect and flag anomalous weeks separately from evergreen themes.
7. Persist themes/quotes in SQLite; write `data/analysis_report.md`.

### Run

```bash
python scripts/run_analysis.py
```

### Done when

- Chroma persistence works; sampling is reproducible; themes ≤5; each theme has a readable name, ≤250-word card, quotes, and evidence count; anomalous weeks flagged.

**Status:** 🟡 Partial — embeddings/search storage now uses **Chroma**, but the full Stage A/B Groq theme-discovery path is still future alignment work.

---

## Phase 5 — Segments & Needs

**Goal:** Infer directional user segments and rank unmet needs from review signal.
**Depends on:** Phase 4
**Maps to:** System Architecture §5.4

### Build steps

1. `analysis/segments.py` — approximate segments from rating tier, free/premium text mentions, tenure language, version/device cues. Each: name, % review volume, top frustration, representative quote. (Directional, not personas.)
2. `analysis/needs.py` — extract "I wish / I want / why can't / please add" statements; rank by frequency + evidence strength (Low/Medium/High) with 2–3 excerpts each.
3. Persist segment and needs outputs for validation and API.

### Run

```bash
python scripts/run_analysis.py     # extend to emit segments + needs
```

### Done when

- Segment inference is directional and evidence-based; unmet needs ranked and quote-supported.

**Status:** 🟡 Partial — align segment/needs outputs to the schema above.

---

## Phase 6 — Validation & Weekly Pulse (Docs MCP)

**Goal:** Add the deterministic validation layer that gates external writes, draft the weekly pulse with Groq, and deliver it to Google Docs via MCP.
**Depends on:** Phase 4 (themes), Phase 5 (needs)
**Maps to:** System Architecture §5.3 (Stage B), §5.5 (validation), §5.6 (Docs MCP). **No Gmail.**

### Quota-aware approach used in this repo

Because `llama-3.3-70b-versatile` is limited to **30 RPM**, **1K RPD**, **12K TPM**, and **100K TPD**, this phase does **not** send 2,400 raw reviews to Groq.

Instead, the implementation does this:

1. Read the existing Phase 4 outputs already stored in the database (`themes`, `quotes`, `review_themes`).
2. Build a **stratified sample capped at 1,000 reviews** from the processed corpus.
3. Compress that sample into a small evidence pack: **top 3 themes** + **up to 12 candidate quotes**.
4. Make **1 primary Groq call** to draft the weekly pulse.
5. Allow **at most 1 repair retry** only if validation fails.

This keeps the total prompt size small and predictable, so we stay well below the token-per-minute and token-per-day limits.

### Build steps

1. `validation/structural.py` — enforce theme count ≤5 and WeeklyPulse shape (exactly 3 themes / 3 quotes / 3 actions).
2. `validation/length.py` — enforce ≤250 words for the pulse under a fixed counting policy.
3. `validation/provenance.py` — verify every quote ⊆ normalized corpus and carries a valid `review_id`.
4. `validation/pii.py` — block emails, phones, `@handles` across all artifacts.
5. `validation/validator.py` — orchestrate checks; return `accept` or `reject(reasons)`.
6. `delivery/pulse.py` — build the 1,000-review stratified sample, compress it into a quota-safe evidence pack, call Groq for the pulse draft, and retry once if validation fails.
7. `delivery/docs_mcp.py` — deliver validated output through a **host-provided MCP command bridge**; save a local preview when MCP is not configured.
8. `scripts/run_pulse.py` — one command: draft → validate (→ repair) → deliver.
9. `models/schema.py` — persist pulse runs, validation state, and delivery result in `weekly_pulses`.
10. `api/routes/analytics.py` — expose the latest stored pulse so the dashboard can link to it later.

### Run

```bash
python scripts/run_pulse.py            # full run: draft, validate, write Doc if MCP is configured
python scripts/run_pulse.py --dry-run  # validate only, no MCP write
```

### Done when

- Validator rejects non-compliant output with actionable reasons.
- Only validated content reaches the dashboard "final" state and the Docs MCP tool.
- Weekly pulse is written to Google Docs when the MCP command is configured; otherwise a local preview is saved in `data/`.
- Repair retry recovers common failures without re-discovering themes.
- No reviewer-identifying data appears in the pulse or Doc.
- Groq usage stays quota-safe because the candidate set is capped at **1,000 reviews** and each run uses **1 call + max 1 repair retry**.

### Notes / prerequisites

- Requires a Google Docs MCP server configured in the MCP host; credentials live outside the repo (env / secret store).
- Config: lookback weeks, sampling seed/caps, retry counts, product display name.

**Status:** ✅ Built — ready to run in `--dry-run` mode now; real Docs delivery needs the MCP host command configured in the environment.

---

## Phase 7 — API & Search

**Goal:** Backend API and retrieval/search for the dashboard.
**Depends on:** Phase 5 (data), Phase 6 (pulse link)
**Maps to:** System Architecture §5.7, §5.8

### Build steps

1. `api/main.py` (FastAPI) with endpoints: stats, themes, segments, unmet needs, and the latest weekly-pulse Doc link.
2. Search endpoint: semantic (**Chroma**) + keyword, with date filters and latest-first sort.
3. RAG chat endpoint: retrieve from Chroma → Groq answers **only from context** → cite `review_id`s → refuse on empty retrieval. Implemented at `GET /api/chat`.
4. Add API tests and docs.

### Run

```bash
uvicorn api.main:app --reload
# health: http://localhost:8000/health
```

### Done when

- Endpoints return dashboard-ready data; search + chat work with citations; date filters consistent.

**Status:** ✅ Built (`api/`)

---

## Phase 8 — Dashboard

**Goal:** Streamlit dashboard with five tabs and evidence-first presentation.
**Depends on:** Phase 7
**Maps to:** System Architecture §5.8

### Build steps

1. `dashboard/app.py` — tabs: Overview, Themes & Chat, Segments, Unmet Needs, Review Discovery.
2. Overview maps metrics to the six research questions; surface the latest weekly pulse Doc link.
3. Cause search box + shared date-filter bar (latest-first default, presets, custom range).
4. "Based on N reviews" citations with expandable source excerpts.
5. Colorblind-safe palette, readable typography.

### Run

```bash
streamlit run dashboard/app.py
```

### Done when

- All five tabs work on live API data; claims carry review-based citations; UI is accessible.

**Status:** ✅ Built (`dashboard/`)

---

## Phase 9 — Integration & Delivery

**Goal:** Validate end-to-end and prepare the final delivery package.
**Depends on:** Phases 2–8
**Maps to:** System Architecture §8

### Build steps

1. Run the full pipeline: ingestion → processing → embedding/themes → segments/needs → validation → dashboard + weekly Docs pulse.
2. Verify answers to the six research questions.
3. Test search, filters, chat, and weekly pulse generation.
4. Privacy audit for PII (including pulse and Doc).
5. Finalize README, demo script, performance check, bug fixes, repo cleanup.

### Run

```bash
python scripts/init_db.py
python scripts/run_collection.py
python scripts/run_processing.py
python scripts/run_analysis.py
python scripts/run_pulse.py
uvicorn api.main:app --reload
streamlit run dashboard/app.py
pytest tests/ -v
```

### Done when

- System answers the six research questions with evidence-backed outputs.
- Dashboard, chat, and weekly pulse are validated.
- Weekly pulse written to Google Docs via MCP with only validated content.
- No reviewer-identifying data in any surface; documentation complete.

**Status:** ✅ Built (`scripts/validate_integration.py`, `validation/privacy_audit.py`, `docs.md/demo_script.md`)

---

## Dependency Order (quick view)

```
0 Research → 1 Foundation → 2 Ingestion → 3 Processing → 4 Embedding & Themes
→ 5 Segments & Needs → 6 Validation & Weekly Pulse (Docs MCP)
→ 7 API & Search → 8 Dashboard → 9 Integration & Delivery
```

- Phase 6 depends on Phases 4–5 and can run in parallel with Phase 7 once analysis outputs are stable.

---

## Related Documents

| Document | Role |
|---|---|
| `docs.md/Problem Statement.md` | Requirements and constraints (scope source of truth) |
| `System Architecture.md` | System design, components, trust boundaries, data contracts |
| `Phase wise architecture.md` | Phase definitions, objectives, exit criteria |
| `docs.md/Learning Log.md` | Plain-language running log of changes |
