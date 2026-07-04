from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class StatsResponse(BaseModel):
    total_reviews: int
    date_range_start: datetime | None
    date_range_end: datetime | None
    platforms: Dict[str, int]


class MetricsResponse(BaseModel):
    total_reviews: int
    complaint_count: int
    average_rating: float | None
    rating_count: int


class ThemeResponse(BaseModel):
    id: str
    name: str
    readable_name: str | None
    description: str | None
    review_count: int
    overall_sentiment: str
    confidence_score: float | None
    summary: str | None
    root_cause: str | None
    top_keywords: List[str]
    date_range_start: datetime
    date_range_end: datetime

    model_config = ConfigDict(from_attributes=True)


class SentimentResponse(BaseModel):
    positive: int
    neutral: int
    negative: int


class InsightResponse(BaseModel):
    id: str
    theme_id: str
    category: str
    summary: str
    supporting_review_count: int
    opportunity_score: float | None
    generated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class QuoteResponse(BaseModel):
    id: str
    theme_id: str
    excerpt: str
    source_platform: str
    is_representative: bool

    model_config = ConfigDict(from_attributes=True)


class ReviewResponse(BaseModel):
    id: str
    platform: str
    content: str
    posted_at: datetime
    sentiment: str | None
    user_segment: str | None
    anonymized_author: str

    model_config = ConfigDict(from_attributes=True)


class SearchResponse(BaseModel):
    query: str
    total_matches: int
    results: List[ReviewResponse]


# ── Research Questions models ────────────────────────────────────────────

class SegmentedTheme(BaseModel):
    name: str
    review_count: int
    sentiment: str
    segment: str  # e.g. "🔴 High Friction", "🔥 Trending Now"
    keywords: List[str]


class QuoteSnippet(BaseModel):
    excerpt: str
    platform: str
    review_id: str | None


class QuestionAnswerResponse(BaseModel):
    id: str
    question: str
    answer_summary: str
    criticality_rating: int  # 1–5 stars
    criticality_score: float
    supporting_review_count: int
    top_themes: List[SegmentedTheme]
    representative_quotes: List[QuoteSnippet]
    sentiment_breakdown: Dict[str, int]


class QuestionsResponse(BaseModel):
    platform_filter: str | None
    answers: List[QuestionAnswerResponse]


class PipelineStatusResponse(BaseModel):
    status: str
    last_synced: datetime | None
    total_reviews: int
    themes_count: int


class WeeklyPulseResponse(BaseModel):
    id: str
    run_id: str
    title: str
    headline: str
    summary: str
    top_themes: List[dict]
    quotes: List[dict]
    actions: List[str]
    sample_review_count: int
    source_review_count: int
    word_count: int
    validation_passed: bool
    validation_errors: List[str]
    delivery_mode: str
    delivery_status: str
    document_id: str | None
    document_url: str | None
    date_range_start: datetime | None
    date_range_end: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

