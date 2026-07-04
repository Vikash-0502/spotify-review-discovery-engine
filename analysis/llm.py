"""Lightweight LLM helpers for theme naming and segment classification.

Uses Anthropic Claude when `CLAUDE_API_KEY` is set in the environment. If
not available, falls back to simple heuristics to avoid breaking the pipeline.
"""
from typing import List, Dict
import os
import logging
import json
import requests

logger = logging.getLogger(__name__)

# Anthropic client (optional)
_USE_ANTHROPIC = False
_client = None
try:
    from anthropic import Anthropic, HUMAN_PROMPT, AI_PROMPT
    api_key = os.environ.get("CLAUDE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        _client = Anthropic(api_key=api_key)
        _USE_ANTHROPIC = True
except Exception:
    _USE_ANTHROPIC = False

# Groq support via HTTP if GROQ_API_KEY provided; keep optional to avoid hard dependency
_USE_GROQ = bool(os.environ.get("GROQ_API_KEY"))
GROQ_API_URL = os.environ.get("GROQ_API_URL", "https://api.groq.ai/v1/completions")
GROQ_MODEL_DEFAULT = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
# Llama provider (HTTP) support. Use when `LLAMA_API_KEY` is set.
_USE_LLAMA = bool(os.environ.get("LLAMA_API_KEY"))
LLAMA_API_URL = os.environ.get("LLAMA_API_URL", "https://api.llama.ai/v1/completions")
LLAMA_MODEL_DEFAULT = os.environ.get("LLAMA_MODEL", "llama-3.3-70b-versatile")


def get_active_provider() -> str:
    """Return the active LLM provider configured in the environment."""
    if _USE_LLAMA:
        return "llama"
    if _USE_GROQ:
        return "groq"
    if _USE_ANTHROPIC:
        return "claude"
    return "none"


def _call_claude(prompt: str, max_tokens: int = 300) -> str:
    if not _USE_ANTHROPIC or _client is None:
        logger.debug("Anthropic not configured; returning empty string for prompt.")
        return ""
    resp = _client.completions.create(
        model="claude-2.1",
        prompt=HUMAN_PROMPT + prompt + AI_PROMPT,
        max_tokens_to_sample=max_tokens,
        temperature=0.0,
    )
    return resp.completion


def _call_groq(prompt: str, max_tokens: int = 300) -> str:
    """Call Groq-style completions via HTTP. Requires `GROQ_API_KEY` env var.

    This is a best-effort implementation that posts JSON to `GROQ_API_URL`.
    If Groq isn't configured or the request fails, returns empty string.
    """
    if not _USE_GROQ:
        logger.debug("Groq not configured; skipping.")
        return ""
    try:
        headers = {"Authorization": f"Bearer {os.environ.get('GROQ_API_KEY')}", "Content-Type": "application/json"}
        payload = {
            "model": os.environ.get("GROQ_MODEL", "groq-mini"),
            "input": prompt,
            "max_output_tokens": max_tokens,
        }
        r = requests.post(GROQ_API_URL, headers=headers, data=json.dumps(payload), timeout=20)
        r.raise_for_status()
        data = r.json()
        # Try common fields
        if isinstance(data, dict):
            if "output" in data and isinstance(data["output"], list):
                return "\n".join(str(x) for x in data["output"])[:10000]
            if "text" in data:
                return str(data["text"])[:10000]
            # Some Groq responses nest completion in choices
            if "choices" in data and data["choices"]:
                return str(data["choices"][0].get("text") or data["choices"][0].get("message") or "")
        return ""
    except Exception:
        logger.exception("Groq API call failed")
        return ""


def _call_llama(prompt: str, max_tokens: int = 300) -> str:
    """Call a generic Llama-compatible HTTP completion endpoint using LLAMA_API_KEY."""
    if not _USE_LLAMA:
        logger.debug("Llama not configured; skipping.")
        return ""
    try:
        headers = {"Authorization": f"Bearer {os.environ.get('LLAMA_API_KEY')}", "Content-Type": "application/json"}
        payload = {
            "model": os.environ.get("LLAMA_MODEL", LLAMA_MODEL_DEFAULT),
            "input": prompt,
            "max_output_tokens": max_tokens,
        }
        r = requests.post(LLAMA_API_URL, headers=headers, data=json.dumps(payload), timeout=30)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict):
            # common response shapes
            if "output" in data and isinstance(data["output"], list):
                return "\n".join(str(x) for x in data["output"])[:10000]
            if "text" in data:
                return str(data["text"])[:10000]
            if "choices" in data and data["choices"]:
                return str(data["choices"][0].get("text") or data["choices"][0].get("message") or "")
        return ""
    except Exception:
        logger.exception("Llama API call failed")
        return ""


def summarize_theme(keywords: List[str], sample_reviews: List[str]) -> Dict[str, str]:
    """Return theme_name, summary, root_cause. Fallback to heuristics if LLM missing."""
    prompt = (
        "Given these representative reviews from a cluster, write a short, specific, "
        "human-readable theme name (5-8 words max) that captures the core user complaint or need. "
        "Then write a one-sentence summary and a concise root cause.\n\n"
        f"Reviews: {sample_reviews}\n"
        f"Top keywords: {keywords}\n\n"
        "Return JSON exactly like: {\n  \"theme_name\": \"...\",\n  \"summary\": \"...\",\n  \"root_cause\": \"...\"\n}\n"
    )

    out = _call_claude(prompt)
    if not out and _USE_GROQ:
        out = _call_groq(prompt, max_tokens=400)
    if out:
        # Try to extract JSON substring naive way
        import json
        try:
            start = out.find("{")
            end = out.rfind("}")
            if start != -1 and end != -1:
                j = json.loads(out[start : end + 1])
                return {
                    "theme_name": j.get("theme_name") or j.get("name") or "" ,
                    "summary": j.get("summary") or "",
                    "root_cause": j.get("root_cause") or j.get("root_cause_summary") or "",
                }
        except Exception:
            logger.exception("Failed to parse LLM output for summarize_theme")

    # Fallback heuristic
    name = " ".join(k for k in (keywords or [])[:6])
    summary = sample_reviews[0][:200] if sample_reviews else ""
    root = "Likely caused by issues in recommendation logic or UX discoverability."
    return {"theme_name": name, "summary": summary, "root_cause": root}


def extract_keywords_with_llm(documents: List[str], existing_keywords: List[str] | None = None, max_keywords: int = 8) -> List[str]:
    """Ask an LLM to read sample documents and return a concise list of theme keywords.

    Tries Anthropic, then Groq. Returns a list of keywords (strings). On failure,
    returns `existing_keywords` or an empty list.
    """
    prompt = (
        "Extract a short list of distinct, descriptive keywords (single words or short phrases) "
        "that summarize the main issue(s) across these user reviews. Return a JSON array of strings only. "
        "Do not return stopwords or generic pronouns.\n\n"
        f"Reviews: {documents[:8]}\n"
        f"Existing keywords: {existing_keywords}\n"
        f"Desired count: {max_keywords}\n"
    )

    out = _call_claude(prompt, max_tokens=200)
    if not out and _USE_GROQ:
        out = _call_groq(prompt, max_tokens=300)

    if out:
        try:
            # try to locate a JSON array in the output
            start = out.find("[")
            end = out.rfind("]")
            if start != -1 and end != -1:
                arr = json.loads(out[start : end + 1])
                if isinstance(arr, list):
                    kws = [str(x).strip() for x in arr if isinstance(x, (str,))]
                    return [k for k in kws if len(k) > 1][:max_keywords]
        except Exception:
            logger.exception("Failed to parse keywords array from LLM output")

    return existing_keywords or []


def _call_llm(prompt: str, max_tokens: int = 300) -> str:
    # Prefer Llama when configured, then Groq, then Anthropic Claude as fallback
    out = ""
    if _USE_LLAMA:
        out = _call_llama(prompt, max_tokens=max_tokens)
        if out:
            logger.info("Using Llama model for completion")
    if not out and _USE_GROQ:
        out = _call_groq(prompt, max_tokens=max_tokens)
        if out:
            logger.info("Using Groq model for completion")
    if not out:
        out = _call_claude(prompt, max_tokens=max_tokens)
    return out.strip() if out else ""


def _parse_json_response(text: str) -> dict:
    import json
    try:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            return json.loads(text[start : end + 1])
    except Exception:
        logger.exception("Failed to parse JSON response from LLM")
    return {}


def generate_theme_name(keywords: List[str], sample_reviews: List[str]) -> str:
    prompt = (
        "Given these reviews from a single cluster, generate a short theme name (5-8 words) that precisely describes the user complaint pattern. "
        "Return only the theme name, nothing else."
        f"\n\nTop keywords: {keywords}\n\n"
        f"Reviews: {sample_reviews}"
    )
    out = _call_llm(prompt, max_tokens=120)
    if out:
        return out.splitlines()[0].strip().strip('"')
    return ""


def generate_cluster_finding(keywords: List[str], sample_reviews: List[str], review_count: int, avg_rating: float | None = None, neg_pct: float | None = None) -> dict:
    def build_prompt(strict: bool = False) -> str:
        # Format sample reviews as a numbered list and build prompt using safe concatenation
        formatted = "\n".join([f"{i+1}. {t[:300]}" for i, t in enumerate((sample_reviews or [])[:5])])
        # Log inputs for debugging (first 200 chars of joined samples)
        try:
            joined_preview = (" ".join(sample_reviews)[:200]) if sample_reviews else ""
        except Exception:
            joined_preview = str(sample_reviews)[:200]
        logger.info("LLM input preview - samples: %s | keywords: %s | review_count: %s", joined_preview, keywords, review_count)

        prompt = (
            "You are a product researcher writing concise findings from real user reviews. Be specific. Never use generic phrases like 'specific problem' or 'harming discovery'. Always name the actual complaint.\n\n"
            + "Theme keywords: " + ", ".join((keywords or [])[:5]) + "\n\n"
            + "Sample reviews:\n"
            + formatted
            + "\n\n"
            + "Review count: " + str(review_count) + "\n"
            + "Average rating: " + (str(avg_rating) if avg_rating is not None else "N/A") + " stars\n"
            + "Negative sentiment: " + (str(neg_pct) if neg_pct is not None else "N/A") + "%\n\n"
            + "Write exactly 2 sentences:\n"
            + "Sentence 1: Name the specific user complaint this cluster represents and mention the review count naturally. Max 25 words.\n"
            + "Sentence 2: Describe the impact this has on the user's listening or discovery experience. Max 20 words. Be specific to music/Spotify context.\n\n"
            + "Return JSON exactly like: {\n  \"title\": \"...\",\n  \"impact\": \"...\"\n}"
        )
        if strict:
            prompt += "\nDo not use generic phrases. You must reference the actual complaint from the review text provided."
        return prompt

    def parse_and_validate(text: str) -> dict | None:
        data = _parse_json_response(text)
        title = data.get("title", "").strip().strip('"')
        impact = data.get("impact", "").strip().strip('"')
        if not title or not impact:
            return None
        bad_phrases = ["specific problem", "harming discovery", "affected listeners"]
        combined = (title + ' ' + impact).lower()
        if any(phrase in combined for phrase in bad_phrases):
            logger.warning("LLM FALLBACK DETECTED for cluster (contains generic phrases). Replacing with keyword-based fallback.")
            # Provide a deterministic fallback using the provided keywords and review_count
            fallback = f"{review_count} reviews cluster around the topics: {', '.join((keywords or [])[:5])}."
            return {"title": fallback, "impact": ""}
        return {"title": title, "impact": impact}

    out = _call_llm(build_prompt(strict=False), max_tokens=280)
    result = parse_and_validate(out) if out else None
    if not result:
        out = _call_llm(build_prompt(strict=True), max_tokens=280)
        result = parse_and_validate(out) if out else None
    if result:
        return result

    return {
        "title": f"{review_count} users describe a real complaint in this cluster.",
        "impact": "This issue is causing friction in music discovery and playback." 
    }


def generate_overall_sentiment_summary(theme_names: List[str], positive: int, neutral: int, negative: int, total_reviews: int, overall_avg_rating: float | None = None) -> str:
    names_text = "\n".join([f"- {name}" for name in theme_names[:8]])
    prompt = (
        "You are a product researcher. Given these top themes and aggregate sentiment stats, write one concise sentence summarizing the overall user sentiment and what it means for music discovery on Spotify. Be specific, not generic. Max 30 words. Return only the sentence.\n\n"
        "These are the top themes found in Spotify user reviews:\n"
        f"{names_text}\n\n"
        "Overall corpus stats:\n"
        f"- Total reviews: {total_reviews}\n"
        f"- Overall negative sentiment: {round(negative / max(total_reviews, 1) * 100)}%\n"
        f"- Average rating: {overall_avg_rating if overall_avg_rating is not None else 'N/A'}\n"
    )
    out = _call_llm(prompt, max_tokens=140)
    if out:
        return out.splitlines()[0].strip().strip('"')
    if total_reviews == 0:
        return "No review sentiment is available for the selected filters."
    negative_pct = round(negative / max(total_reviews, 1) * 100)
    if negative_pct >= 55:
        return "Overall sentiment is strongly negative and users are largely dissatisfied with the current experience."
    if negative_pct >= 35:
        return "Sentiment is mixed, with clear dissatisfaction around core music discovery and playback flows."
    return "Most users feel somewhat satisfied, but there are still notable friction points in the experience."


SEGMENT_LABELS = [
    "Casual/habit listener",
    "Active music seeker",
    "Mood/context listener",
    "Genre loyalist",
]


def classify_review_segment(review_text: str) -> str:
    """Classify a single review into one of the fixed user segments.

    Uses LLM when available; otherwise uses keyword heuristics.
    """
    prompt = (
        "Classify the following user review into one of these segments: "
        "Casual/habit listener, Active music seeker, Mood/context listener, Genre loyalist. "
        "Return only the segment name.\n\n"
        f"Review: {review_text}\n"
    )
    out = _call_claude(prompt, max_tokens=60)
    if not out and _USE_GROQ:
        out = _call_groq(prompt, max_tokens=120)
    if out:
        # sanitize
        for label in SEGMENT_LABELS:
            if label.lower() in out.lower():
                return label

    # Heuristic fallback
    txt = review_text.lower()
    if any(w in txt for w in ["gym", "study", "commute", "workout", "mood"]):
        return "Mood/context listener"
    if any(w in txt for w in ["discover", "find", "new artist", "explore"]):
        return "Active music seeker"
    if any(w in txt for w in ["genre", "language", "only listen", "rock", "pop", "hip hop", "country"]):
        return "Genre loyalist"
    return "Casual/habit listener"


def generate_question_answer(question: str, representative_quotes: List[str]) -> str:
    """Produce a 2-3 sentence AI answer for a research question using sample quotes."""
    prompt = (
        f"Answer this research question in 2-3 sentences, grounded in the quotes below. "
        f"Question: {question}\nQuotes: {representative_quotes}\nReturn plain text answer."
    )
    out = _call_claude(prompt, max_tokens=200)
    if not out and _USE_GROQ:
        out = _call_groq(prompt, max_tokens=300)
    if out:
        return out.strip()
    # Fallback simple synthesis
    if representative_quotes:
        return "Based on user quotes, issues appear around " + representative_quotes[0][:160]
    return "Not enough evidence to generate a concise answer."
