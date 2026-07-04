"""Grounded RAG answers for discovery chat."""

from __future__ import annotations

import re
from datetime import datetime

import requests
from sqlalchemy.orm import Session

from analysis.question_mapper import RESEARCH_QUESTIONS, map_questions_to_themes
from analysis.retrieval import retrieve_reviews_hybrid
from models.schema import Insight, Quote, Review, ReviewTheme, Theme
from utils.config import Settings, get_settings
from utils.logging import get_logger

logger = get_logger(__name__)

REFUSAL_MESSAGE = (
    "Not enough review signal was found for this question in the current filter set. "
    "Try broadening the date range or changing the source filter."
)


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def _call_groq_chat(system_prompt: str, user_prompt: str, settings: Settings, max_tokens: int = 400) -> str:
    if not settings.groq_api_key:
        return ""

    estimated = _estimate_tokens(system_prompt) + _estimate_tokens(user_prompt)
    if estimated + max_tokens > settings.groq_tokens_per_minute:
        logger.warning("Skipping Groq chat call because prompt exceeds token budget.")
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
        logger.exception("Groq chat call failed")
        return ""


def _load_question_context(
    db: Session,
    from_date: datetime | None,
    to_date: datetime | None,
    platform: str | None,
) -> tuple[list[dict], list[dict], list[dict]]:
    theme_query = db.query(Theme)
    if platform:
        theme_ids_query = (
            db.query(ReviewTheme.theme_id)
            .join(Review, ReviewTheme.review_id == Review.id)
            .filter(Review.platform == platform)
            .distinct()
        )
        theme_query = theme_query.filter(Theme.id.in_(theme_ids_query))
    if from_date:
        theme_query = theme_query.filter(Theme.created_at >= from_date)
    if to_date:
        theme_query = theme_query.filter(Theme.created_at <= to_date)

    themes = [
        {
            "id": theme.id,
            "name": theme.name,
            "description": theme.description,
            "review_count": theme.review_count,
            "overall_sentiment": theme.overall_sentiment,
            "confidence_score": theme.confidence_score,
            "top_keywords": theme.top_keywords or [],
            "date_range_start": theme.date_range_start.isoformat() if theme.date_range_start else None,
            "date_range_end": theme.date_range_end.isoformat() if theme.date_range_end else None,
        }
        for theme in theme_query.all()
    ]

    insight_query = db.query(Insight)
    if from_date:
        insight_query = insight_query.filter(Insight.generated_at >= from_date)
    if to_date:
        insight_query = insight_query.filter(Insight.generated_at <= to_date)
    insights = [
        {
            "id": insight.id,
            "theme_id": insight.theme_id,
            "category": insight.category,
            "summary": insight.summary,
            "supporting_review_count": insight.supporting_review_count,
            "opportunity_score": insight.opportunity_score,
        }
        for insight in insight_query.all()
    ]

    quote_query = db.query(Quote).join(Review)
    if from_date:
        quote_query = quote_query.filter(Review.posted_at >= from_date)
    if to_date:
        quote_query = quote_query.filter(Review.posted_at <= to_date)
    if platform:
        quote_query = quote_query.filter(Quote.source_platform == platform)
    quotes = [
        {
            "id": quote.id,
            "theme_id": quote.theme_id,
            "excerpt": quote.excerpt,
            "source_platform": quote.source_platform,
            "review_id": quote.review_id,
        }
        for quote in quote_query.limit(200).all()
    ]
    return themes, insights, quotes


def _match_research_question(question: str, mapped_answers: list[dict]) -> dict | None:
    normalized = question.strip().lower()
    for answer in mapped_answers:
        mapped_question = answer.get("question", "").lower()
        if mapped_question in normalized or normalized in mapped_question:
            return answer
    for item in RESEARCH_QUESTIONS:
        mapped_question = item["question"].lower()
        if mapped_question in normalized or normalized in mapped_question:
            for answer in mapped_answers:
                if answer.get("id") == item["id"]:
                    return answer
    return None


def _build_citations(reviews: list[Review], limit: int = 5) -> list[dict]:
    citations = []
    for review in reviews[:limit]:
        citations.append(
            {
                "review_id": review.id,
                "excerpt": review.content[:320].strip(),
                "platform": review.platform,
                "posted_at": review.posted_at,
                "sentiment": review.sentiment,
            }
        )
    return citations


def _fallback_answer(question: str, reviews: list[Review]) -> str:
    snippets = [review.content[:180].strip() for review in reviews[:3] if review.content]
    if not snippets:
        return REFUSAL_MESSAGE
    joined = "; ".join(f'"{snippet}..."' for snippet in snippets)
    return (
        f"Based on {len(reviews)} retrieved reviews, users highlight issues such as {joined} "
        f"when answering: {question}"
    )


def _extract_cited_review_ids(answer: str, allowed_ids: set[str]) -> list[str]:
    cited = []
    for match in re.findall(r"review_id[=:\s]+([A-Za-z0-9_-]+)", answer, flags=re.IGNORECASE):
        if match in allowed_ids and match not in cited:
            cited.append(match)
    for review_id in allowed_ids:
        if review_id in answer and review_id not in cited:
            cited.append(review_id)
    return cited[:5]


def generate_grounded_answer(question: str, reviews: list[Review], settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    if not reviews:
        return REFUSAL_MESSAGE

    context_blocks = []
    for review in reviews[:6]:
        excerpt = review.content[:320].strip()
        context_blocks.append(f"[review_id={review.id}] platform={review.platform} :: {excerpt}")
    context = "\n\n".join(context_blocks)

    system_prompt = (
        "You are a Spotify review discovery analyst. Answer ONLY using the review excerpts provided. "
        "Do not use general Spotify knowledge. Cite review_id values in square brackets when making claims. "
        "If the excerpts do not contain enough evidence, say there is not enough signal."
    )
    user_prompt = (
        f"Question: {question}\n\n"
        f"Review excerpts:\n{context}\n\n"
        "Write a concise 2-4 sentence answer grounded only in the excerpts above."
    )

    answer = _call_groq_chat(system_prompt, user_prompt, settings)
    if answer:
        return answer
    return _fallback_answer(question, reviews)


def answer_discovery_chat(
    db: Session,
    question: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    platform: str | None = None,
    limit: int = 6,
    settings: Settings | None = None,
) -> dict:
    settings = settings or get_settings()
    question = question.strip()
    if len(question) < 2:
        return {
            "question": question,
            "answer": "Please enter a question with at least two characters.",
            "refused": True,
            "based_on_review_count": 0,
            "criticality_rating": 1,
            "citations": [],
            "related_themes": [],
            "source": "validation",
        }

    themes, insights, quotes = _load_question_context(db, from_date, to_date, platform)
    mapped_answers = map_questions_to_themes(themes, insights, quotes)
    matched = _match_research_question(question, mapped_answers)
    if matched:
        return {
            "question": question,
            "answer": matched["answer_summary"],
            "refused": False,
            "based_on_review_count": matched.get("supporting_review_count", 0),
            "criticality_rating": matched.get("criticality_rating", 3),
            "citations": [
                {
                    "review_id": quote.get("review_id"),
                    "excerpt": quote.get("excerpt", ""),
                    "platform": quote.get("platform", ""),
                    "posted_at": None,
                    "sentiment": None,
                }
                for quote in matched.get("representative_quotes", [])[:5]
            ],
            "related_themes": [theme.get("name", "") for theme in matched.get("top_themes", [])[:5]],
            "source": "research_question_map",
        }

    reviews, total_matches = retrieve_reviews_hybrid(
        db,
        question,
        from_date=from_date,
        to_date=to_date,
        platform=platform,
        limit=limit,
    )
    if not reviews:
        return {
            "question": question,
            "answer": REFUSAL_MESSAGE,
            "refused": True,
            "based_on_review_count": 0,
            "criticality_rating": 1,
            "citations": [],
            "related_themes": [],
            "source": "retrieval_empty",
        }

    answer = generate_grounded_answer(question, reviews, settings=settings)
    allowed_ids = {review.id for review in reviews}
    cited_ids = _extract_cited_review_ids(answer, allowed_ids)
    citation_reviews = [review for review in reviews if review.id in cited_ids] or reviews[:3]

    negative_count = sum(1 for review in reviews if review.sentiment == "negative")
    criticality_rating = 3
    if negative_count >= max(1, len(reviews) // 2):
        criticality_rating = 4
    if negative_count == len(reviews) and len(reviews) >= 2:
        criticality_rating = 5

    return {
        "question": question,
        "answer": answer,
        "refused": False,
        "based_on_review_count": len(reviews),
        "total_matches": total_matches,
        "criticality_rating": criticality_rating,
        "citations": _build_citations(citation_reviews),
        "related_themes": [],
        "source": "rag_retrieval",
    }
