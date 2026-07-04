"""Hybrid semantic + keyword review retrieval for search and RAG."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from analysis.embeddings import get_embedding_model
from analysis.vector_store import query_similar_review_ids
from models.schema import Review


def apply_review_filters(
    query,
    from_date: datetime | None,
    to_date: datetime | None,
    platform: str | None,
    date_column,
):
    if from_date:
        query = query.filter(date_column >= from_date)
    if to_date:
        query = query.filter(date_column <= to_date)
    if platform:
        query = query.filter(Review.platform == platform)
    return query


def retrieve_reviews_hybrid(
    db: Session,
    query_text: str,
    *,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    platform: str | None = None,
    limit: int = 20,
) -> tuple[list[Review], int]:
    """Return ranked reviews using semantic Chroma search plus keyword matches."""
    base_query = db.query(Review)
    base_query = apply_review_filters(base_query, from_date, to_date, platform, Review.posted_at)

    keyword_matches = base_query.filter(Review.content.ilike(f"%{query_text}%")).all()
    keyword_ids = {review.id for review in keyword_matches}

    model = get_embedding_model()
    query_emb = model.encode(query_text)
    semantic_hits = query_similar_review_ids(
        query_embedding=query_emb,
        top_k=max(limit * 5, 25),
        where={"platform": platform} if platform else None,
    )

    scored_reviews: list[tuple[float, Review]] = []
    semantic_ids = [review_id for review_id, _ in semantic_hits]

    if semantic_ids:
        semantic_query = db.query(Review).filter(Review.id.in_(semantic_ids))
        semantic_query = apply_review_filters(
            semantic_query, from_date, to_date, platform, Review.posted_at
        )
        semantic_reviews = {review.id: review for review in semantic_query.all()}

        for review_id, score in semantic_hits:
            review = semantic_reviews.get(review_id)
            if not review:
                continue
            if review.id in keyword_ids:
                score += 0.2
            if score > 0.3:
                scored_reviews.append((score, review))

    scored_ids = {review.id for _, review in scored_reviews}
    for review in keyword_matches:
        if review.id not in scored_ids:
            scored_reviews.append((0.5, review))

    scored_reviews.sort(
        key=lambda item: (item[0], item[1].posted_at.timestamp() if item[1].posted_at else 0),
        reverse=True,
    )
    top_reviews = [review for _, review in scored_reviews[:limit]]
    return top_reviews, len(scored_reviews)
