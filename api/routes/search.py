from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from analysis.embeddings import get_embedding_model
from analysis.vector_store import query_similar_review_ids
from api.routes.analytics import apply_date_filter
from api.schemas import ReviewResponse, SearchResponse
from models.database import get_db_session
from models.schema import Review

router = APIRouter(tags=["Search"])


@router.get("/search", response_model=SearchResponse)
def search(
    q: str = Query(..., min_length=2),
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    platform: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db_session),
):
    query = db.query(Review)
    query = apply_date_filter(query, Review, from_date, to_date, Review.posted_at)
    if platform:
        query = query.filter(Review.platform == platform)

    # 1. Keyword search (fast baseline)
    keyword_matches = query.filter(Review.content.ilike(f"%{q}%")).all()

    # 2. Semantic search via Chroma
    model = get_embedding_model()
    query_emb = model.encode(q)
    semantic_hits = query_similar_review_ids(
        query_embedding=query_emb,
        top_k=max(limit * 5, 25),
        where={"platform": platform} if platform else None,
    )

    scored_reviews = []
    keyword_ids = {r.id for r in keyword_matches}
    semantic_ids = [review_id for review_id, _ in semantic_hits]

    if semantic_ids:
        semantic_query = db.query(Review).filter(Review.id.in_(semantic_ids))
        semantic_query = apply_date_filter(semantic_query, Review, from_date, to_date, Review.posted_at)
        if platform:
            semantic_query = semantic_query.filter(Review.platform == platform)
        semantic_reviews = {review.id: review for review in semantic_query.all()}

        for review_id, score in semantic_hits:
            rev = semantic_reviews.get(review_id)
            if not rev:
                continue
            if rev.id in keyword_ids:
                score += 0.2
            if score > 0.3:
                scored_reviews.append((score, rev))

    scored_ids = {r.id for _, r in scored_reviews}
    for rev in keyword_matches:
        if rev.id not in scored_ids:
            # Fallback for exact matches that didn't pass semantic threshold
            scored_reviews.append((0.5, rev))

    scored_reviews.sort(key=lambda x: x[0], reverse=True)
    top_reviews = [rev for _, rev in scored_reviews[:limit]]

    return SearchResponse(
        query=q,
        total_matches=len(scored_reviews),
        results=top_reviews,
    )


@router.get("/reviews/{id}", response_model=ReviewResponse)
def get_review(id: str, db: Session = Depends(get_db_session)):
    review = db.query(Review).filter(Review.id == id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review
