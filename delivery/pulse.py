"""Phase 6 weekly pulse orchestration."""

from __future__ import annotations

import json
import math
import random
import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import requests

from delivery.docs_mcp import DeliveryResult, deliver_weekly_pulse
from models.database import get_session_factory, init_db
from models.schema import Quote, Review, ReviewTheme, Theme, WeeklyPulse
from utils.config import PROJECT_ROOT, get_settings
from utils.logging import get_logger
from validation.validator import ValidationResult, validate_weekly_pulse

logger = get_logger(__name__)


@dataclass
class PulseRunResult:
    run_id: str
    title: str
    sample_review_count: int
    source_review_count: int
    validation: ValidationResult
    delivery: DeliveryResult | None
    output_path: str


def _rating_tier(review: Review) -> str:
    if review.rating is None:
        return "neutral"
    if review.rating <= 2:
        return "negative"
    if review.rating == 3:
        return "neutral"
    return "positive"


def _estimate_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def _normalize_json_payload(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        logger.warning("Failed to parse Groq JSON response.")
        return {}


def _select_sample_reviews(reviews: list[Review], limit: int, seed: int) -> list[Review]:
    buckets: dict[tuple[str, str], list[Review]] = defaultdict(list)
    for review in reviews:
        iso = review.posted_at.isocalendar()
        week_key = f"{iso.year}-W{iso.week:02d}"
        buckets[(week_key, _rating_tier(review))].append(review)

    rng = random.Random(seed)
    for bucket_reviews in buckets.values():
        bucket_reviews.sort(key=lambda item: item.posted_at, reverse=True)
        rng.shuffle(bucket_reviews)

    weeks = sorted({week for week, _ in buckets}, reverse=True)
    sample: list[Review] = []
    seen_ids: set[str] = set()

    while len(sample) < limit:
        added_this_round = 0
        for week in weeks:
            for tier in ("negative", "negative", "neutral", "positive"):
                bucket = buckets.get((week, tier), [])
                while bucket and bucket[0].id in seen_ids:
                    bucket.pop(0)
                if bucket and len(sample) < limit:
                    review = bucket.pop(0)
                    if review.id not in seen_ids:
                        sample.append(review)
                        seen_ids.add(review.id)
                        added_this_round += 1
                if len(sample) >= limit:
                    break
            if len(sample) >= limit:
                break
        if added_this_round == 0:
            break

    return sample


def _build_theme_evidence(session, sample_reviews: list[Review], top_n: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    sample_ids = [review.id for review in sample_reviews]
    if not sample_ids:
        return [], []

    links = (
        session.query(ReviewTheme, Theme)
        .join(Theme, ReviewTheme.theme_id == Theme.id)
        .filter(ReviewTheme.review_id.in_(sample_ids))
        .all()
    )
    theme_counts = Counter(link.theme_id for link, _ in links)
    review_lookup = {review.id: review for review in sample_reviews}
    theme_lookup: dict[str, Theme] = {}
    theme_to_review_ids: dict[str, list[str]] = defaultdict(list)
    for link, theme in links:
        theme_lookup[theme.id] = theme
        theme_to_review_ids[theme.id].append(link.review_id)

    top_theme_ids = [theme_id for theme_id, _ in theme_counts.most_common(top_n)]
    theme_payloads: list[dict[str, Any]] = []
    candidate_quotes: list[dict[str, Any]] = []

    for theme_id in top_theme_ids:
        theme = theme_lookup[theme_id]
        theme_review_ids = theme_to_review_ids.get(theme_id, [])
        theme_reviews = [review_lookup[rid] for rid in theme_review_ids if rid in review_lookup]

        quotes = (
            session.query(Quote)
            .filter(Quote.theme_id == theme_id, Quote.review_id.in_(theme_review_ids))
            .order_by(Quote.is_representative.desc())
            .limit(3)
            .all()
        )

        if not quotes:
            for review in theme_reviews[:3]:
                candidate_quotes.append(
                    {
                        "review_id": review.id,
                        "excerpt": review.content[:240].strip(),
                        "platform": review.platform,
                        "theme_name": theme.readable_name or theme.name,
                    }
                )
        else:
            for quote in quotes:
                source_review = review_lookup.get(quote.review_id)
                source_text = source_review.content.strip() if source_review else quote.excerpt.strip()
                stored_excerpt = quote.excerpt.strip()
                if stored_excerpt and stored_excerpt.lower() in source_text.lower():
                    excerpt = stored_excerpt
                else:
                    excerpt = source_text[:180].strip()
                candidate_quotes.append(
                    {
                        "review_id": quote.review_id,
                        "excerpt": excerpt,
                        "platform": quote.source_platform,
                        "theme_name": theme.readable_name or theme.name,
                    }
                )

        theme_payloads.append(
            {
                "theme_id": theme.id,
                "name": theme.readable_name or theme.name,
                "summary": theme.summary or theme.description or "",
                "root_cause": theme.root_cause or "",
                "review_count": theme_counts[theme_id],
                "overall_sentiment": theme.overall_sentiment,
                "top_keywords": theme.top_keywords[:6] if isinstance(theme.top_keywords, list) else [],
            }
        )

    deduped_quotes: list[dict[str, Any]] = []
    seen_pairs: set[tuple[str, str]] = set()
    for quote in candidate_quotes:
        key = (quote["review_id"], quote["excerpt"])
        if key in seen_pairs:
            continue
        seen_pairs.add(key)
        deduped_quotes.append(quote)

    return theme_payloads, deduped_quotes


def _build_action_fallback(theme_payloads: list[dict[str, Any]], limit: int) -> list[str]:
    actions: list[str] = []
    for theme in theme_payloads[:limit]:
        root_cause = str(theme.get("root_cause", "")).strip()
        if root_cause:
            actions.append(f"Investigate: {root_cause[:60].rstrip('.')}.")
        else:
            actions.append(f"Review fixes for {theme['name'].lower()}.")
    while len(actions) < limit:
        actions.append("Prioritize the highest-volume discovery complaint.")
    return actions[:limit]


def _fallback_pulse(evidence: dict[str, Any], settings) -> dict[str, Any]:
    top_themes = [
        {
            "name": theme["name"],
            "why_it_matters": (
                theme.get("summary")
                or theme.get("root_cause")
                or "This issue appears repeatedly in recent reviews."
            )[:70].rstrip("."),
        }
        for theme in evidence["top_themes"][: settings.pulse_theme_limit]
    ]
    quotes = [
        {"review_id": quote["review_id"], "excerpt": quote["excerpt"]}
        for quote in evidence["candidate_quotes"][: settings.pulse_quote_limit]
    ]
    actions = _build_action_fallback(evidence["top_themes"], settings.pulse_action_limit)
    theme_names = ", ".join(theme["name"] for theme in evidence["top_themes"][:3]) or "recent discovery issues"
    return {
        "headline": "Weekly Spotify review pulse",
        "summary": (
            f"Recent Spotify reviews point mainly to {theme_names}. "
            f"This pulse uses a quota-safe sample of {evidence['sample_review_count']} reviews."
        ),
        "top_themes": top_themes,
        "quotes": quotes,
        "actions": actions,
    }


def _build_groq_prompt(evidence: dict[str, Any], settings) -> tuple[str, str]:
    system_prompt = (
        "You are a product research analyst. Write a compact weekly pulse from structured evidence only. "
        "Do not invent quotes. Use only the supplied quotes exactly as written. "
        "Return valid JSON only."
    )

    user_payload = {
        "constraints": {
            "top_themes_exactly": settings.pulse_theme_limit,
            "quotes_exactly": settings.pulse_quote_limit,
            "actions_exactly": settings.pulse_action_limit,
            "max_words_total": settings.pulse_max_words,
            "theme_names_limit": "short readable names",
        },
        "sample_metadata": {
            "source_review_count": evidence["source_review_count"],
            "sample_review_count": evidence["sample_review_count"],
            "date_range_start": evidence["date_range_start"],
            "date_range_end": evidence["date_range_end"],
            "sentiment_breakdown": evidence["sentiment_breakdown"],
            "model_limits": {
                "requests_per_minute": settings.groq_requests_per_minute,
                "tokens_per_minute": settings.groq_tokens_per_minute,
            },
        },
        "themes": evidence["top_themes"],
        "candidate_quotes": evidence["candidate_quotes"][:12],
        "required_json_schema": {
            "headline": "string",
            "summary": "string",
            "top_themes": [{"name": "string", "why_it_matters": "string"}],
            "quotes": [{"review_id": "string", "excerpt": "string"}],
            "actions": ["string"],
        },
        "instructions": [
            "Use exactly 3 themes, 3 quotes, and 3 action ideas.",
            "Copy quotes exactly from candidate_quotes; do not paraphrase them.",
            "Keep the entire response under the word limit.",
            "Focus on discovery, recommendations, repetition, shuffle, and related user pain points if present.",
        ],
    }
    return system_prompt, json.dumps(user_payload, ensure_ascii=True, indent=2)


def _call_groq(system_prompt: str, user_prompt: str, settings, max_tokens: int = 500) -> str:
    if not settings.groq_api_key:
        return ""

    estimated_input_tokens = _estimate_tokens(system_prompt) + _estimate_tokens(user_prompt)
    if estimated_input_tokens + max_tokens > settings.groq_tokens_per_minute:
        logger.warning(
            "Groq prompt budget too large (%s estimated tokens). Falling back to deterministic pulse.",
            estimated_input_tokens + max_tokens,
        )
        return ""

    payload = {
        "model": settings.groq_model,
        "temperature": 0,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    headers = {
        "Authorization": f"Bearer {settings.groq_api_key}",
        "Content-Type": "application/json",
    }

    try:
        response = requests.post(
            settings.groq_api_url,
            headers=headers,
            json=payload,
            timeout=settings.pulse_docs_timeout_seconds,
        )
        response.raise_for_status()
        data = response.json()
        return (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        ).strip()
    except Exception:
        logger.exception("Groq pulse request failed.")
        return ""


def _repair_prompt(original_user_prompt: str, errors: list[str]) -> str:
    return (
        original_user_prompt
        + "\n\nValidation failed for these reasons:\n- "
        + "\n- ".join(errors)
        + "\n\nReturn corrected JSON only. Do not change quotes unless needed to exactly match a provided candidate quote."
    )


def _render_markdown(title: str, pulse: dict[str, Any], evidence: dict[str, Any]) -> str:
    lines = [
        f"# {title}",
        "",
        f"**Sampled reviews:** {evidence['sample_review_count']} of {evidence['source_review_count']}",
        f"**Date range:** {evidence['date_range_start']} to {evidence['date_range_end']}",
        "",
        f"## {pulse['headline']}",
        "",
        pulse["summary"],
        "",
        "## Top Themes",
        "",
    ]

    for theme in pulse["top_themes"]:
        lines.append(f"- **{theme['name']}** — {theme['why_it_matters']}")

    lines.extend(["", "## Evidence Quotes", ""])
    for quote in pulse["quotes"]:
        lines.append(f'- "{quote["excerpt"]}" (`{quote["review_id"]}`)')

    lines.extend(["", "## Action Ideas", ""])
    for action in pulse["actions"]:
        lines.append(f"- {action}")

    return "\n".join(lines)


def _build_evidence(session, settings) -> tuple[dict[str, Any], dict[str, str]]:
    reviews = (
        session.query(Review)
        .filter(Review.sentiment.isnot(None))
        .order_by(Review.posted_at.desc())
        .all()
    )
    if not reviews:
        raise ValueError("No processed reviews with sentiment found. Run processing and analysis first.")

    source_review_count = len(reviews)
    sampled_reviews = _select_sample_reviews(
        reviews,
        limit=min(settings.pulse_review_cap, source_review_count),
        seed=settings.pulse_sampling_seed,
    )
    theme_payloads, candidate_quotes = _build_theme_evidence(
        session, sampled_reviews, top_n=settings.pulse_theme_limit
    )
    if len(theme_payloads) < settings.pulse_theme_limit:
        raise ValueError("Not enough themes found to generate a weekly pulse.")
    if len(candidate_quotes) < settings.pulse_quote_limit:
        raise ValueError("Not enough representative quotes found to generate a weekly pulse.")

    review_lookup = {review.id: review.content for review in sampled_reviews}
    sentiment_breakdown = Counter((review.sentiment or "neutral") for review in sampled_reviews)
    posted_dates = [review.posted_at for review in sampled_reviews]
    evidence = {
        "source_review_count": source_review_count,
        "sample_review_count": len(sampled_reviews),
        "date_range_start": min(posted_dates).date().isoformat(),
        "date_range_end": max(posted_dates).date().isoformat(),
        "sentiment_breakdown": dict(sentiment_breakdown),
        "top_themes": theme_payloads,
        "candidate_quotes": candidate_quotes,
    }
    return evidence, review_lookup


def run_weekly_pulse(*, dry_run: bool = False) -> PulseRunResult:
    init_db()
    settings = get_settings()
    session = get_session_factory()()
    run_id = str(uuid.uuid4())

    try:
        evidence, review_lookup = _build_evidence(session, settings)
        title = f"Spotify Weekly Pulse ({evidence['date_range_start']} to {evidence['date_range_end']})"
        system_prompt, user_prompt = _build_groq_prompt(evidence, settings)
        raw_response = _call_groq(system_prompt, user_prompt, settings)
        pulse = _normalize_json_payload(raw_response) if raw_response else {}
        if not pulse:
            pulse = _fallback_pulse(evidence, settings)
            raw_response = json.dumps(pulse, ensure_ascii=True)

        validation = validate_weekly_pulse(
            pulse,
            review_lookup=review_lookup,
            theme_limit=settings.pulse_theme_limit,
            quote_limit=settings.pulse_quote_limit,
            action_limit=settings.pulse_action_limit,
            max_words=settings.pulse_max_words,
        )

        retries = 0
        while (
            not validation.is_valid
            and settings.groq_api_key
            and retries < settings.pulse_max_retries
        ):
            retries += 1
            repair_response = _call_groq(
                system_prompt,
                _repair_prompt(user_prompt, validation.errors),
                settings,
            )
            repaired = _normalize_json_payload(repair_response)
            if repaired:
                pulse = repaired
                raw_response = repair_response
                validation = validate_weekly_pulse(
                    pulse,
                    review_lookup=review_lookup,
                    theme_limit=settings.pulse_theme_limit,
                    quote_limit=settings.pulse_quote_limit,
                    action_limit=settings.pulse_action_limit,
                    max_words=settings.pulse_max_words,
                )

        markdown = _render_markdown(title, pulse, evidence)
        output_path = PROJECT_ROOT / "data" / "weekly_pulse_report.md"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(markdown, encoding="utf-8")

        pulse_row = WeeklyPulse(
            run_id=run_id,
            title=title,
            headline=pulse["headline"],
            summary=pulse["summary"],
            top_themes=pulse["top_themes"],
            quotes=pulse["quotes"],
            actions=pulse["actions"],
            sample_review_count=evidence["sample_review_count"],
            source_review_count=evidence["source_review_count"],
            word_count=validation.word_count,
            model_name=settings.groq_model if settings.groq_api_key else "deterministic-fallback",
            prompt_version=settings.pulse_prompt_version,
            validation_passed=validation.is_valid,
            validation_errors=validation.errors,
            raw_response=raw_response,
            date_range_start=datetime.fromisoformat(evidence["date_range_start"]),
            date_range_end=datetime.fromisoformat(evidence["date_range_end"]),
        )

        delivery_result: DeliveryResult | None = None
        if validation.is_valid:
            delivery_result = deliver_weekly_pulse(
                title=title,
                markdown=markdown,
                settings=settings,
                dry_run=dry_run,
            )
            pulse_row.delivery_mode = delivery_result.mode
            pulse_row.delivery_status = delivery_result.status
            pulse_row.document_id = delivery_result.document_id
            pulse_row.document_url = delivery_result.document_url
        else:
            pulse_row.delivery_mode = "none"
            pulse_row.delivery_status = "blocked_by_validation"

        session.add(pulse_row)
        session.commit()

        return PulseRunResult(
            run_id=run_id,
            title=title,
            sample_review_count=evidence["sample_review_count"],
            source_review_count=evidence["source_review_count"],
            validation=validation,
            delivery=delivery_result,
            output_path=str(output_path),
        )
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
