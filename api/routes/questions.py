"""API endpoint for research question answers with criticality ratings."""

from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from analysis.question_mapper import map_questions_to_themes
from api.schemas import QuestionsResponse, QuestionAnswerResponse
from models.database import get_db_session
from models.schema import Insight, Quote, Review, ReviewTheme, Theme

router = APIRouter(tags=["Research Questions"])


@router.get("/questions", response_model=QuestionsResponse)
def get_question_answers(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    platform: str | None = Query(None, description="Filter by platform: play_store, app_store, spotify_community"),
    db: Session = Depends(get_db_session),
):
    """Return AI-generated answers for each of the 6 research questions,
    ranked by criticality score (most critical first)."""

    # ── Fetch themes, optionally filtered by platform ──
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

    themes_db = theme_query.all()
    themes = [
        {
            "id": t.id,
            "name": t.name,
            "description": t.description,
            "review_count": t.review_count,
            "overall_sentiment": t.overall_sentiment,
            "confidence_score": t.confidence_score,
            "top_keywords": t.top_keywords or [],
            "date_range_start": t.date_range_start.isoformat() if t.date_range_start else None,
            "date_range_end": t.date_range_end.isoformat() if t.date_range_end else None,
        }
        for t in themes_db
    ]

    # ── Fetch insights ──
    insight_query = db.query(Insight)
    if from_date:
        insight_query = insight_query.filter(Insight.generated_at >= from_date)
    if to_date:
        insight_query = insight_query.filter(Insight.generated_at <= to_date)
    if platform:
        insight_query = insight_query.filter(Insight.theme_id.in_(
            db.query(ReviewTheme.theme_id)
            .join(Review, ReviewTheme.review_id == Review.id)
            .filter(Review.platform == platform)
            .distinct()
        ))

    insights_db = insight_query.all()
    insights = [
        {
            "id": i.id,
            "theme_id": i.theme_id,
            "category": i.category,
            "summary": i.summary,
            "supporting_review_count": i.supporting_review_count,
            "opportunity_score": i.opportunity_score,
        }
        for i in insights_db
    ]

    # ── Fetch representative quotes ──
    quote_query = db.query(Quote).filter(Quote.is_representative == True)
    if platform:
        quote_query = quote_query.filter(Quote.source_platform == platform)

    quotes_db = quote_query.all()
    quotes = [
        {
            "id": q.id,
            "theme_id": q.theme_id,
            "excerpt": q.excerpt,
            "source_platform": q.source_platform,
            "review_id": q.review_id,
        }
        for q in quotes_db
    ]

    # ── Map questions to themes and compute answers ──
    answers = map_questions_to_themes(themes, insights, quotes)

    return QuestionsResponse(
        platform_filter=platform,
        answers=answers,
    )
