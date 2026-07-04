# **Problem Statement**

AI-Powered Review Discovery Engine — Spotify

## **1. Background**

Spotify has acquired hundreds of millions of users globally and operates one of the most advanced music recommendation systems in the world. Yet despite this sophistication, a significant share of listening remains repetitive — users returning to the same playlists, familiar artists, and previously heard tracks rather than genuinely discovering new music.

This is not a lack of data. Spotify has more listening signal than almost any product in existence. The gap is one of **insight translation** — the distance between what users are experiencing and what the product team can systematically hear, interpret, and act on at scale.

User frustration with discovery is expressed daily across Play Store reviews, App Store reviews, Reddit threads, and community forums. But this feedback is unstructured, scattered, and impossible to analyze meaningfully without a systematic, AI-powered approach.

## **2. The Core Problem**

*Product teams currently have no reliable, evidence-based system to understand — directly from user voices at scale — why discovery is failing, who it is failing for, and what users are actually trying to achieve.*

Any solution built without this foundation risks being driven by internal assumptions rather than real user signal. The result: features that address symptoms rather than root causes, and discovery improvements that miss the users who need them most.

## **3. What This Engine Must Answer**

The review discovery engine must surface clear, grounded, and evidence-cited answers to the following six questions — derived directly from the review corpus:

| # | Research Question |
|---|---|
| 1 | Why do users struggle to discover new music on Spotify? |
| 2 | What are the most common frustrations with Spotify's recommendation system? |
| 3 | What listening behaviors and goals are users actually trying to achieve? |
| 4 | What causes users to fall into repetitive listening loops? |
| 5 | Which user segments experience discovery challenges differently? |
| 6 | What unmet needs appear consistently across the review corpus? |

## **4. System Scope & Functional Requirements**

### **4.1 Ingestion**

Pull 8–12 weeks of Spotify Play Store reviews (configurable date range), capturing rating, review title/text, date, app version, and thumbs-up count. Source: public Play Store export only — no login-gated scraping, no ToS-violating automation.

### **4.2 Normalization**

Clean review text (strip whitespace, HTML artifacts, repeated characters). Drop emoji-only reviews, sub-threshold word-count entries, and near-duplicates. Retain English-only reviews, flag non-English for future expansion. Remove all PII — no usernames, device IDs, or emails in any artifact.

### **4.3 Embedding + Vector Store**

Embed normalized reviews using sentence-transformers/all-MiniLM-L6-v2 (local, zero Groq quota cost). Persist to a local Chroma vector store — file-persisted and swappable for a hosted store later.

### **4.4 Theme Discovery**

Cluster reviews into a maximum of 5 themes relevant to discovery and recommendation behavior. Each theme surfaces as a Groq-generated narrative card (≤250 words), a human-readable name (not raw keywords), representative quotes with review_id citations, and a trend-over-time view. Anomalous weeks must be flagged separately — not absorbed into evergreen narratives.

### **4.5 Segment View**

Approximate user segments from review signal: rating tier, free/premium text mentions, tenure language, and device/version signals. Segments are directional behavioral clusters, not ground-truth personas. Each shows: name, % of review volume, top frustration, and a representative quote.

### **4.6 Unmet Needs Extraction**

Distill recurring 'I wish / I want / why can't / please add' statements into a ranked list of unmet needs. Each need shows: frequency count, evidence strength (Low/Medium/High), and 2–3 source review excerpts.

### **4.7 Dashboard (Streamlit)**

Five tabs: Overview, Themes & Chat, Segments, Unmet Needs, Review Discovery. Overview tab maps key metrics directly to the 6 research questions. All AI-generated claims display a 'Based on N reviews' citation tag with expandable source excerpts. Colorblind-safe palette, minimum contrast compliance, readable font sizes throughout.

### **4.8 RAG-Grounded Chatbot**

Q&A widget powered by Groq (llama-3.3-70b-versatile). Answers only from retrieved review content — no open-domain speculation. Every answer cites source review_ids. Explicit refusal / 'not enough signal' behavior when retrieval is empty. Starter questions pre-mapped to the 6 research questions.

## **5. Tech Stack**

| Component | Choice | Rationale |
|---|---|---|
| LLM (generation) | Groq (llama-3.3-70b-versatile) | Fast inference, generous free tier |
| Embeddings | sentence-transformers/all-MiniLM-L6-v2 | Local, zero Groq quota cost |
| Vector Store | Chroma (local, file-persisted) | Simple, swappable |
| Dashboard | Streamlit | Fast to ship, Cursor-friendly |
| Data Source | Play Store public export | ToS-compliant, no auth required |

## **6. Key Constraints**

- **Max 5 theme clusters:** Focus forces sharper, more actionable insights
- **Privacy-first:** No usernames, emails, device IDs, or reviewer-identifying data anywhere — including chatbot responses (cite by review_id only)
- **Quota discipline:** Groq rate/token limits (RPM/RPD/TPM/TPD) must shape all batching logic
- **Grounding is non-negotiable:** Chatbot never answers from general Spotify knowledge — only from retrieved review content
- **Scannability:** Theme narrative cards capped at 250 words; charts and quotes are separate from this cap

## **7. Known Limitations**

- **No free/premium ground truth:** Segmentation is text-inferred — treat as directional, not authoritative
- **No reviewer demographics:** Segments are behavioral and text-derived, not verified personas
- **Review skew risk:** External events (outages, price changes, regressions) can spike negative reviews — anomalous weeks must be flagged, not blended
- **English-only corpus:** Multilingual reviews are filtered in v1 — limits coverage of non-English-speaking user segments

## **8. Current Build Status (v1.2)**

**Operational:**

- ✅ Multi-source ingestion (Google Play, App Store, Community Forums)
- ✅ Theme clustering with friction scoring
- ✅ Segment view (friction-based)
- ✅ RAG-grounded Discovery Chat with review_id citations
- ✅ Raw Review Discovery Search (semantic + keyword)
- ✅ Pipeline online indicator with last-sync timestamp

**In Progress / Needs Upgrade:**

- ⚠️ Theme labels are raw keyword fragments — need Groq-generated human-readable names
- ⚠️ Segments tab shows topic clusters, not behavioral user segments
- ⚠️ Overview tab not mapped to the 6 research questions
- ⚠️ Unmet Needs tab needs frequency ranking and evidence strength scoring
- ⚠️ Chart contrast and colorblind-safe palette not yet applied
- ⚠️ Anomalous week flagging not implemented

## **9. Definition of Done**

The engine is complete when a product manager with no technical background can:

1. Open the dashboard and immediately understand the top 5 discovery pain themes with evidence
2. Ask any of the 6 research questions in the chatbot and receive a grounded, cited answer
3. Identify which user segment is most affected by discovery failure and why
4. Export a ranked list of unmet needs to inform the Part 3 problem definition
5. Trust that every claim shown is traceable to a real user review
