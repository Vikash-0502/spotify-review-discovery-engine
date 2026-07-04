"""Maps research questions to themes/insights and computes criticality ratings."""

from collections import Counter
from datetime import datetime, timedelta, timezone

RESEARCH_QUESTIONS = [
    {
        "id": "q1",
        "question": "Why do users struggle to discover new music?",
        "keywords": [
            "discover", "new music", "explore", "find", "browse", "discovery",
            "new artist", "new song", "fresh", "unfamiliar",
        ],
    },
    {
        "id": "q2",
        "question": "What are the most common frustrations with recommendations?",
        "keywords": [
            "recommend", "algorithm", "suggestion", "repetitive", "same songs",
            "repeat", "boring", "irrelevant", "bad recommendation", "wrong",
        ],
    },
    {
        "id": "q3",
        "question": "What listening behaviors are users trying to achieve?",
        "keywords": [
            "playlist", "shuffle", "radio", "queue", "autoplay", "listen",
            "skip", "mix", "daily mix", "release radar", "discover weekly",
        ],
    },
    {
        "id": "q4",
        "question": "What causes users to repeatedly listen to the same content?",
        "keywords": [
            "repeat", "same", "loop", "stuck", "echo chamber", "bubble",
            "over and over", "again", "always the same", "never new",
        ],
    },
    {
        "id": "q5",
        "question": "Which user segments experience different discovery challenges?",
        "keywords": [
            "premium", "free", "new user", "long-time", "casual", "power user",
            "subscriber", "paid", "plan", "family", "student",
        ],
    },
    {
        "id": "q6",
        "question": "What unmet needs emerge consistently across reviews?",
        "keywords": [
            "wish", "want", "need", "missing", "should", "would be nice",
            "hope", "please add", "feature", "request", "improve",
        ],
    },
]


# ── Segmentation labels ──────────────────────────────────────────────────

def compute_segment_label(neg_ratio: float, review_count: int, recency_days: int | None) -> str:
    """Assign a human-readable segment label to a theme group.

    Labels (in priority order):
      - "🔴 High Friction"       — >60 % negative sentiment
      - "🟠 Moderate Friction"   — 40-60 % negative
      - "🔥 Trending Now"        — most recent reviews within 30 days
      - "🟢 Positive Signal"     — <20 % negative
      - "⚪ Low Signal"          — everything else
    """
    if neg_ratio >= 0.60:
        return "🔴 High Friction"
    if neg_ratio >= 0.40:
        return "🟠 Moderate Friction"
    if recency_days is not None and recency_days <= 30:
        return "🔥 Trending Now"
    if neg_ratio < 0.20:
        return "🟢 Positive Signal"
    return "⚪ Low Signal"


def _sentiment_weight(sentiment: str) -> float:
    return {"negative": 1.0, "neutral": 0.5, "positive": 0.2}.get(sentiment, 0.5)


# ── Core mapper ──────────────────────────────────────────────────────────

def _keyword_score(text: str, keywords: list[str]) -> int:
    """Count how many keywords appear in text (case-insensitive)."""
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw.lower() in text_lower)


def map_questions_to_themes(
    themes: list[dict],
    insights: list[dict],
    quotes: list[dict],
) -> list[dict]:
    """For each research question, find relevant themes, compute criticality,
    build a summary, and return sorted by criticality (most critical first).

    Args:
        themes:  list of dicts with keys: id, name, description, review_count,
                 overall_sentiment, confidence_score, top_keywords,
                 date_range_start, date_range_end
        insights: list of dicts with keys: id, theme_id, category, summary,
                  supporting_review_count, opportunity_score
        quotes:  list of dicts with keys: id, theme_id, excerpt, source_platform

    Returns:
        list of question-answer dicts sorted by criticality_score desc.
    """
    now = datetime.now(timezone.utc)
    insight_by_theme: dict[str, list[dict]] = {}
    for ins in insights:
        insight_by_theme.setdefault(ins["theme_id"], []).append(ins)

    quote_by_theme: dict[str, list[dict]] = {}
    for q in quotes:
        quote_by_theme.setdefault(q["theme_id"], []).append(q)

    results = []

    for qdef in RESEARCH_QUESTIONS:
        # Score each theme against this question's keywords
        matched_themes = []
        for theme in themes:
            searchable = (
                (theme.get("name") or "")
                + " " + (theme.get("description") or "")
                + " " + " ".join(theme.get("top_keywords") or [])
            )
            score = _keyword_score(searchable, qdef["keywords"])
            if score > 0:
                matched_themes.append((score, theme))

        matched_themes.sort(key=lambda x: x[0], reverse=True)

        total_reviews = sum(t["review_count"] for _, t in matched_themes)

        # Compute criticality: weighted review count
        criticality_raw = 0.0
        sentiment_counts: dict[str, int] = {"negative": 0, "neutral": 0, "positive": 0}
        for _, t in matched_themes:
            w = _sentiment_weight(t["overall_sentiment"])
            criticality_raw += t["review_count"] * w
            sentiment_counts[t["overall_sentiment"]] = (
                sentiment_counts.get(t["overall_sentiment"], 0) + t["review_count"]
            )

        # Normalize criticality to 1–5 star scale (will be normalized across questions later)
        criticality_score = criticality_raw

        # Gather representative quotes from matched themes
        rep_quotes = []
        for _, t in matched_themes[:5]:
            for q in quote_by_theme.get(t["id"], [])[:2]:
                rep_quotes.append(q)
            if len(rep_quotes) >= 3:
                break

        # Gather top theme names
        top_theme_names = [t["name"] for _, t in matched_themes[:5]]

        # Compute segment labels for matched themes
        segmented_themes = []
        for _, t in matched_themes[:5]:
            neg_count = sentiment_counts.get("negative", 0)
            total = max(t["review_count"], 1)
            neg_ratio = neg_count / max(total_reviews, 1) if total_reviews else 0.0
            # Per-theme neg ratio
            theme_neg_ratio = 1.0 if t["overall_sentiment"] == "negative" else (
                0.5 if t["overall_sentiment"] == "neutral" else 0.0
            )
            # Recency
            end_date = t.get("date_range_end")
            recency_days = None
            if end_date:
                if isinstance(end_date, str):
                    try:
                        end_date = datetime.fromisoformat(end_date)
                    except Exception:
                        end_date = None
                if end_date:
                    # Ensure timezone-aware for comparison
                    if end_date.tzinfo is None:
                        end_date = end_date.replace(tzinfo=timezone.utc)
                    try:
                        recency_days = (now - end_date).days
                    except Exception:
                        recency_days = None
                    if isinstance(recency_days, int) and recency_days < 0:
                        recency_days = 0

            segment = compute_segment_label(theme_neg_ratio, t["review_count"], recency_days)
            segmented_themes.append({
                "name": t["name"],
                "review_count": t["review_count"],
                "sentiment": t["overall_sentiment"],
                "segment": segment,
                "keywords": (t.get("top_keywords") or [])[:5],
            })

        # Build AI summary
        summary = _build_question_summary(
            qdef["question"], matched_themes, total_reviews, sentiment_counts
        )

        results.append({
            "id": qdef["id"],
            "question": qdef["question"],
            "answer_summary": summary,
            "criticality_score": criticality_score,
            "supporting_review_count": total_reviews,
            "top_themes": segmented_themes,
            "representative_quotes": [
                {"excerpt": q["excerpt"], "platform": q["source_platform"], "review_id": q.get("review_id")}
                for q in rep_quotes[:3]
            ],
            "sentiment_breakdown": sentiment_counts,
        })

    # Normalize criticality to 1–5 star scale
    max_crit = max((r["criticality_score"] for r in results), default=1.0) or 1.0
    for r in results:
        r["criticality_rating"] = max(1, min(5, round(r["criticality_score"] / max_crit * 5)))

    # Sort by criticality (most critical first)
    results.sort(key=lambda x: x["criticality_score"], reverse=True)
    return results


def _build_question_summary(
    question: str,
    matched_themes: list[tuple[int, dict]],
    total_reviews: int,
    sentiment_counts: dict[str, int],
) -> str:
    """Build a plain-English answer paragraph from matched data."""
    if not matched_themes:
        return (
            f"Not enough data to answer this question confidently. "
            f"The current review dataset does not contain strong signals for this topic."
        )

    top_names = [t["name"] for _, t in matched_themes[:3]]
    neg = sentiment_counts.get("negative", 0)
    pos = sentiment_counts.get("positive", 0)
    total = max(total_reviews, 1)
    neg_pct = round(neg / total * 100)

    theme_list = ", ".join(f"'{n}'" for n in top_names[:3])

    summary = (
        f"Based on {total_reviews:,} relevant reviews, the main themes are {theme_list}. "
    )

    if neg_pct >= 60:
        summary += (
            f"User feedback is overwhelmingly negative ({neg_pct}%), indicating this is a "
            f"critical friction area that significantly impacts user satisfaction. "
        )
    elif neg_pct >= 40:
        summary += (
            f"Sentiment is mixed but leans negative ({neg_pct}% negative), suggesting "
            f"notable user frustration that warrants attention. "
        )
    elif neg_pct >= 20:
        summary += (
            f"Sentiment is relatively balanced ({neg_pct}% negative), with both positive "
            f"and negative perspectives present. "
        )
    else:
        summary += (
            f"Feedback is mostly positive ({100 - neg_pct}% non-negative), though some "
            f"users still report issues. "
        )

    if len(matched_themes) > 3:
        summary += (
            f"Additionally, {len(matched_themes) - 3} more themes relate to this question."
        )

    return summary
