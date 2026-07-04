from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from analysis.retrieval import retrieve_reviews_hybrid
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
    results, total_matches = retrieve_reviews_hybrid(
        db,
        q,
        from_date=from_date,
        to_date=to_date,
        platform=platform,
        limit=limit,
    )
    return SearchResponse(
        query=q,
        total_matches=total_matches,
        results=results,
    )


@router.get("/reviews/{id}", response_model=ReviewResponse)
def get_review(id: str, db: Session = Depends(get_db_session)):
    review = db.query(Review).filter(Review.id == id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review
