from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy import func
from sqlalchemy.orm import Session

from api.schemas import (
    InsightResponse, QuoteResponse, SentimentResponse, StatsResponse,
    MetricsResponse, ThemeResponse, ReviewResponse, PipelineStatusResponse,
    WeeklyPulseResponse,
)
from models.database import get_db_session
from models.schema import Insight, Quote, Review, ReviewTheme, Theme, WeeklyPulse
from analysis.pipeline import run_analysis

router = APIRouter(tags=["Analytics"])


def apply_date_filter(query, model, from_date: datetime | None, to_date: datetime | None, date_column):
    if from_date:
        query = query.filter(date_column >= from_date)
    if to_date:
        query = query.filter(date_column <= to_date)
    return query


@router.get("/stats", response_model=StatsResponse)
def get_stats(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    platform: str | None = Query(None, description="Filter by platform: play_store, app_store, spotify_community"),
    db: Session = Depends(get_db_session)
):
    query = db.query(Review)
    query = apply_date_filter(query, Review, from_date, to_date, Review.posted_at)
    if platform:
        query = query.filter(Review.platform == platform)

    total_reviews = query.count()

    # Date range for filtered set
    date_q = db.query(func.min(Review.posted_at), func.max(Review.posted_at))
    date_q = apply_date_filter(date_q, Review, from_date, to_date, Review.posted_at)
    if platform:
        date_q = date_q.filter(Review.platform == platform)
    date_range = date_q.first()
    start_date, end_date = date_range if date_range else (None, None)

    # Platform counts (always show all for comparison, but scoped by date)
    plat_q = db.query(Review.platform, func.count(Review.id)).group_by(Review.platform)
    plat_q = apply_date_filter(plat_q, Review, from_date, to_date, Review.posted_at)
    if platform:
        plat_q = plat_q.filter(Review.platform == platform)
    platform_counts = plat_q.all()
    platforms = {p: count for p, count in platform_counts}

    return StatsResponse(
        total_reviews=total_reviews,
        date_range_start=start_date,
        date_range_end=end_date,
        platforms=platforms
    )


@router.get("/metrics", response_model=MetricsResponse)
def get_metrics(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    platform: str | None = Query(None, description="Filter by platform: play_store, app_store, spotify_community"),
    db: Session = Depends(get_db_session)
):
    query = db.query(Review)
    query = apply_date_filter(query, Review, from_date, to_date, Review.posted_at)
    if platform:
        query = query.filter(Review.platform == platform)
    total_reviews = query.count()

    complaint_query = db.query(func.count(Review.id)).filter(Review.sentiment == "negative")
    complaint_query = apply_date_filter(complaint_query, Review, from_date, to_date, Review.posted_at)
    if platform:
        complaint_query = complaint_query.filter(Review.platform == platform)
    complaint_count = complaint_query.scalar() or 0

    rating_avg_query = db.query(func.avg(Review.rating))
    rating_avg_query = apply_date_filter(rating_avg_query, Review, from_date, to_date, Review.posted_at)
    if platform:
        rating_avg_query = rating_avg_query.filter(Review.platform == platform)
    average_rating = rating_avg_query.scalar()

    rating_count_query = db.query(func.count(Review.id)).filter(Review.rating.isnot(None))
    rating_count_query = apply_date_filter(rating_count_query, Review, from_date, to_date, Review.posted_at)
    if platform:
        rating_count_query = rating_count_query.filter(Review.platform == platform)
    rating_count = rating_count_query.scalar() or 0

    return MetricsResponse(
        total_reviews=total_reviews,
        complaint_count=complaint_count,
        average_rating=round(average_rating, 2) if average_rating is not None else None,
        rating_count=rating_count,
    )


@router.get("/themes", response_model=List[ThemeResponse])
def get_themes(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    platform: str | None = Query(None, description="Filter by platform"),
    sort: str = Query("latest", description="Sort by 'latest' or 'oldest' (creation date of theme)"),
    limit: int = 16,
    db: Session = Depends(get_db_session)
):
    if platform:
        # Find themes that have reviews from this platform
        theme_ids_query = (
            db.query(ReviewTheme.theme_id)
            .join(Review, ReviewTheme.review_id == Review.id)
            .filter(Review.platform == platform)
            .distinct()
        )
        query = db.query(Theme).filter(Theme.id.in_(theme_ids_query))
    else:
        query = db.query(Theme)

    query = apply_date_filter(query, Theme, from_date, to_date, Theme.created_at)

    if sort == "latest":
        query = query.order_by(Theme.created_at.desc())
    else:
        query = query.order_by(Theme.created_at.asc())

    themes = query.limit(limit).all()
    return themes


@router.get("/sentiment", response_model=SentimentResponse)
def get_sentiment(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    platform: str | None = Query(None, description="Filter by platform"),
    db: Session = Depends(get_db_session)
):
    query = db.query(Review.sentiment, func.count(Review.id)).group_by(Review.sentiment)
    query = apply_date_filter(query, Review, from_date, to_date, Review.posted_at)
    if platform:
        query = query.filter(Review.platform == platform)

    sentiment_counts = query.all()

    counts = {"positive": 0, "neutral": 0, "negative": 0}
    for sentiment, count in sentiment_counts:
        if sentiment in counts:
            counts[sentiment] = count

    return SentimentResponse(**counts)


@router.get("/pain-points", response_model=List[InsightResponse])
def get_pain_points(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    platform: str | None = Query(None, description="Filter by platform"),
    limit: int = 10,
    db: Session = Depends(get_db_session)
):
    query = db.query(Insight).filter(Insight.category == "pain_point")
    query = apply_date_filter(query, Insight, from_date, to_date, Insight.generated_at)

    if platform:
        # Filter insights by themes that have reviews from this platform
        theme_ids_query = (
            db.query(ReviewTheme.theme_id)
            .join(Review, ReviewTheme.review_id == Review.id)
            .filter(Review.platform == platform)
            .distinct()
        )
        query = query.filter(Insight.theme_id.in_(theme_ids_query))

    # Sort by opportunity score to rank pain points
    query = query.order_by(Insight.opportunity_score.desc())
    return query.limit(limit).all()


@router.get("/quotes", response_model=List[QuoteResponse])
def get_quotes(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    platform: str | None = Query(None, description="Filter by platform"),
    limit: int = 20,
    db: Session = Depends(get_db_session)
):
    query = db.query(Quote).join(Review)
    query = apply_date_filter(query, Review, from_date, to_date, Review.posted_at)
    if platform:
        query = query.filter(Quote.source_platform == platform)

    query = query.filter(Quote.is_representative == True)
    return query.limit(limit).all()


@router.get("/themes/{theme_id}/reviews", response_model=List[ReviewResponse])
def get_theme_reviews(
    theme_id: str,
    limit: int = 50,
    db: Session = Depends(get_db_session)
):
    query = (
        db.query(Review)
        .join(ReviewTheme, Review.id == ReviewTheme.review_id)
        .filter(ReviewTheme.theme_id == theme_id)
        .order_by(Review.posted_at.desc())
    )
    return query.limit(limit).all()


# Variable to store background pipeline status
pipeline_status = {
    "status": "idle",
    "last_synced": None
}


def background_run_pipeline():
    global pipeline_status
    pipeline_status["status"] = "running"
    try:
        run_analysis(force_themes=True)
        pipeline_status["status"] = "idle"
        pipeline_status["last_synced"] = datetime.now()
    except Exception as e:
        pipeline_status["status"] = f"failed: {str(e)}"


@router.get("/pipeline/status", response_model=PipelineStatusResponse)
def get_pipeline_status(db: Session = Depends(get_db_session)):
    global pipeline_status
    total_reviews = db.query(Review).count()
    themes_count = db.query(Theme).count()
    
    # Fallback if last_synced is None: get last created theme time or current time
    last_synced = pipeline_status["last_synced"]
    if not last_synced:
        last_theme = db.query(Theme.created_at).order_by(Theme.created_at.desc()).first()
        if last_theme:
            last_synced = last_theme[0]
            
    return PipelineStatusResponse(
        status=pipeline_status["status"],
        last_synced=last_synced,
        total_reviews=total_reviews,
        themes_count=themes_count
    )


@router.post("/pipeline/refresh")
def refresh_pipeline(background_tasks: BackgroundTasks):
    global pipeline_status
    if pipeline_status["status"] == "running":
        return {"message": "Pipeline is already running"}
    
    background_tasks.add_task(background_run_pipeline)
    return {"message": "Pipeline run started in background"}


@router.get("/segments")
def get_segments(
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    platform: str | None = Query(None, description="Filter by platform: play_store, app_store, spotify_community"),
    db: Session = Depends(get_db_session),
):
    """Return aggregate counts and representative quote per user segment."""
    query = db.query(Review)
    query = apply_date_filter(query, Review, from_date, to_date, Review.posted_at)
    if platform:
        query = query.filter(Review.platform == platform)

    q = (
        query.with_entities(Review.user_segment, func.count(Review.id))
        .group_by(Review.user_segment)
        .order_by(func.count(Review.id).desc())
    )
    rows = q.all()
    segments = []
    for seg, count in rows:
        rep = (
            db.query(Review.id, Review.content)
            .filter(Review.user_segment == seg)
        )
        rep = apply_date_filter(rep, Review, from_date, to_date, Review.posted_at)
        if platform:
            rep = rep.filter(Review.platform == platform)
        rep = rep.order_by(Review.posted_at.desc()).first()

        rep_excerpt = rep.content if rep else None
        rep_id = rep.id if rep else None
        segments.append({
            "segment": seg or "Unknown",
            "count": count,
            "representative_quote": rep_excerpt,
            "representative_review_id": rep_id,
        })
    return {"segments": segments}


@router.get("/weekly-pulse/latest", response_model=WeeklyPulseResponse | None)
def get_latest_weekly_pulse(db: Session = Depends(get_db_session)):
    return (
        db.query(WeeklyPulse)
        .order_by(WeeklyPulse.created_at.desc())
        .first()
    )

