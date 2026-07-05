"""Persistent pgvector store for review embeddings and retrieval."""

from __future__ import annotations

from datetime import datetime

import numpy as np
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from analysis.embeddings import EMBEDDING_DIM
from models.database import get_session_factory
from models.schema import Review, ReviewEmbedding, utcnow
from utils.config import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)


def _use_session(db: Session | None) -> tuple[Session, bool]:
    if db is not None:
        return db, False
    return get_session_factory()(), True


def clear_review_embeddings(db: Session | None = None) -> None:
    session, own_session = _use_session(db)
    try:
        session.execute(delete(ReviewEmbedding))
        if own_session:
            session.commit()
    finally:
        if own_session:
            session.close()


def clear_review_collection() -> None:
    """Backward-compatible alias for the old Chroma clear helper."""
    clear_review_embeddings()


def upsert_review_embeddings(
    *,
    review_ids: list[str],
    texts: list[str],
    embeddings: np.ndarray,
    metadatas: list[dict] | None = None,
    db: Session | None = None,
) -> int:
    del texts, metadatas  # metadata lives on Review; kept for call-site compatibility
    if not review_ids:
        return 0

    settings = get_settings()
    session, own_session = _use_session(db)
    try:
        rows = [
            {
                "review_id": review_id,
                "embedding_model": settings.embedding_model,
                "embedding_vector": embeddings[idx].astype(float).tolist(),
                "indexed_at": utcnow(),
            }
            for idx, review_id in enumerate(review_ids)
        ]
        stmt = insert(ReviewEmbedding).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=[ReviewEmbedding.review_id],
            set_={
                "embedding_model": stmt.excluded.embedding_model,
                "embedding_vector": stmt.excluded.embedding_vector,
                "indexed_at": stmt.excluded.indexed_at,
            },
        )
        session.execute(stmt)
        if own_session:
            session.commit()
        return len(review_ids)
    finally:
        if own_session:
            session.close()


def get_embeddings_for_reviews(review_ids: list[str], db: Session | None = None) -> np.ndarray:
    if not review_ids:
        return np.empty((0, EMBEDDING_DIM), dtype=np.float32)

    session, own_session = _use_session(db)
    try:
        stmt = select(ReviewEmbedding).where(ReviewEmbedding.review_id.in_(review_ids))
        rows = session.scalars(stmt).all()
        embed_map = {
            row.review_id: np.asarray(row.embedding_vector, dtype=np.float32)
            for row in rows
        }
        ordered_vectors = [embed_map[review_id] for review_id in review_ids if review_id in embed_map]
        if not ordered_vectors:
            return np.empty((0, EMBEDDING_DIM), dtype=np.float32)
        return np.vstack(ordered_vectors)
    finally:
        if own_session:
            session.close()


def query_similar_review_ids(
    *,
    query_embedding: np.ndarray,
    top_k: int,
    platform: str | None = None,
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    where: dict | None = None,
    db: Session | None = None,
) -> list[tuple[str, float]]:
    del where  # legacy Chroma filter arg; use platform/from_date/to_date instead
    session, own_session = _use_session(db)
    try:
        distance = ReviewEmbedding.embedding_vector.cosine_distance(
            query_embedding.astype(float).tolist()
        )
        stmt = (
            select(Review.id, distance.label("distance"))
            .join(ReviewEmbedding, Review.id == ReviewEmbedding.review_id)
        )
        if platform:
            stmt = stmt.where(Review.platform == platform)
        if from_date:
            stmt = stmt.where(Review.posted_at >= from_date)
        if to_date:
            stmt = stmt.where(Review.posted_at <= to_date)
        stmt = stmt.order_by(distance).limit(top_k)

        scored: list[tuple[str, float]] = []
        for review_id, dist in session.execute(stmt).all():
            score = max(0.0, 1.0 - float(dist))
            scored.append((review_id, score))
        return scored
    finally:
        if own_session:
            session.close()


def count_embeddings(db: Session | None = None) -> int:
    session, own_session = _use_session(db)
    try:
        return session.scalar(select(func.count()).select_from(ReviewEmbedding)) or 0
    finally:
        if own_session:
            session.close()
