"""Tests for pgvector-backed embedding store."""

import sys
import uuid
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.embeddings import EMBEDDING_DIM  # noqa: E402
from analysis.vector_store import (  # noqa: E402
    count_embeddings,
    get_embeddings_for_reviews,
    query_similar_review_ids,
    upsert_review_embeddings,
)
from models.schema import RawReview, Review  # noqa: E402


def _insert_review(db_session, content: str = "Discover Weekly keeps repeating songs."):
    raw = RawReview(
        platform="play_store",
        external_id=f"ext-{uuid.uuid4().hex}",
        raw_payload={"content": content},
    )
    db_session.add(raw)
    db_session.flush()
    review = Review(
        raw_review_id=raw.id,
        platform="play_store",
        content=content,
        posted_at=raw.collected_at,
        anonymized_author="user_abc12345",
    )
    db_session.add(review)
    db_session.commit()
    return review


def test_upsert_and_query_embeddings(db_session):
    review = _insert_review(db_session)
    vector = np.random.rand(EMBEDDING_DIM).astype(np.float32)
    upsert_review_embeddings(
        review_ids=[review.id],
        texts=[review.content],
        embeddings=np.array([vector]),
        db=db_session,
    )
    db_session.commit()

    loaded = get_embeddings_for_reviews([review.id], db=db_session)
    assert loaded.shape == (1, EMBEDDING_DIM)

    hits = query_similar_review_ids(
        query_embedding=vector,
        top_k=5,
        db=db_session,
    )
    assert hits
    assert hits[0][0] == review.id
    assert hits[0][1] > 0.9
    assert count_embeddings(db=db_session) >= 1
