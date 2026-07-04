from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from analysis.rag import answer_discovery_chat
from api.schemas import ChatResponse
from models.database import get_db_session

router = APIRouter(tags=["Chat"])


@router.get("/chat", response_model=ChatResponse)
def chat(
    q: str = Query(..., min_length=2, description="Discovery question to answer"),
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    platform: str | None = None,
    limit: int = Query(6, ge=1, le=12),
    db: Session = Depends(get_db_session),
):
    """Grounded RAG chat: retrieve reviews from Chroma, answer with Groq, cite review_ids."""
    result = answer_discovery_chat(
        db,
        q,
        from_date=from_date,
        to_date=to_date,
        platform=platform,
        limit=limit,
    )
    return ChatResponse(**result)
