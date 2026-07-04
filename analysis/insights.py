"""Insight generation from theme clusters."""

from collections import Counter
from datetime import datetime

BEHAVIOR_KEYWORDS = {
    "discover", "playlist", "listen", "shuffle", "radio", "search",
    "explore", "find", "recommend", "autoplay", "skip",
}

SEGMENTATION_PLATFORMS = {"play_store", "app_store", "reddit", "spotify_community"}


def dominant_sentiment(sentiments: list[str]) -> str:
    if not sentiments:
        return "neutral"
    counts = Counter(sentiments)
    return counts.most_common(1)[0][0]


def sentiment_weight(sentiment: str) -> float:
    return {"negative": 1.0, "neutral": 0.5, "positive": 0.2}.get(sentiment, 0.5)


def opportunity_score(review_count: int, sentiment: str) -> float:
    return round(review_count * sentiment_weight(sentiment), 2)


def classify_theme_insights(theme_name: str, keywords: list[str], platforms: list[str]) -> list[str]:
    categories = ["pain_point", "opportunity"]
    keyword_text = " ".join(keywords).lower() + " " + theme_name.lower()

    if any(word in keyword_text for word in BEHAVIOR_KEYWORDS):
        categories.append("behavior")

    platform_counts = Counter(platforms)
    if len(platform_counts) >= 2:
        top_share = platform_counts.most_common(1)[0][1] / max(len(platforms), 1)
        if top_share >= 0.6:
            categories.append("segmentation")

    return list(dict.fromkeys(categories))


def build_insight_summary(category: str, theme_name: str, review_count: int, sentiment: str, platforms: list[str]) -> str:
    platform_note = ""
    if platforms:
        top = Counter(platforms).most_common(1)[0][0]
        platform_note = f" Most feedback comes from {top.replace('_', ' ')}."

    templates = {
        "pain_point": (
            f"Users report issues related to '{theme_name}'. "
            f"{review_count} reviews mention this with predominantly {sentiment} sentiment.{platform_note}"
        ),
        "behavior": (
            f"Users describe how they interact with Spotify around '{theme_name}'. "
            f"This pattern appears in {review_count} reviews.{platform_note}"
        ),
        "segmentation": (
            f"The theme '{theme_name}' affects user groups differently across platforms. "
            f"Based on {review_count} reviews, feedback is unevenly distributed.{platform_note}"
        ),
        "opportunity": (
            f"'{theme_name}' represents a product opportunity based on {review_count} reviews "
            f"with {sentiment} sentiment.{platform_note}"
        ),
    }
    return templates.get(category, templates["pain_point"])


def select_representative_quotes(reviews: list[dict], max_quotes: int = 3, max_length: int = 280) -> list[dict]:
    """Pick diverse, informative quotes — prefer negative sentiment and longer text."""
    scored = []
    for review in reviews:
        text = review["content"].strip()
        if len(text) < 30:
            continue
        score = len(text)
        if review.get("sentiment") == "negative":
            score += 100
        scored.append((score, review))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = []
    seen_starts = set()

    for _, review in scored:
        start = review["content"][:40].lower()
        if start in seen_starts:
            continue
        seen_starts.add(start)
        excerpt = review["content"]
        if len(excerpt) > max_length:
            excerpt = excerpt[: max_length - 3].rstrip() + "..."
        selected.append({**review, "excerpt": excerpt})
        if len(selected) >= max_quotes:
            break

    return selected


def theme_confidence(probabilities: list[float]) -> float:
    if not probabilities:
        return 0.0
    return round(sum(probabilities) / len(probabilities), 3)
