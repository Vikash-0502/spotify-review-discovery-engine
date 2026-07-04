"""Pure dashboard UI helpers (testable without Streamlit runtime)."""


def render_based_on_badge(count: int) -> str:
    safe_count = max(int(count or 0), 0)
    return f'<span class="evidence-badge">Based on {safe_count:,} reviews</span>'


def evidence_strength_label(count: int) -> tuple[str, str]:
    if count >= 50:
        return "High", "strength-high"
    if count >= 15:
        return "Medium", "strength-medium"
    return "Low", "strength-low"


def sentiment_badge(sentiment: str | None) -> str:
    label = (sentiment or "unknown").lower()
    css = {
        "negative": "sent-negative",
        "neutral": "sent-neutral",
        "positive": "sent-positive",
    }.get(label, "sent-neutral")
    text = {
        "negative": "Negative",
        "neutral": "Neutral",
        "positive": "Positive",
    }.get(label, "Unknown")
    return f'<span class="sent-badge {css}">{text}</span>'
