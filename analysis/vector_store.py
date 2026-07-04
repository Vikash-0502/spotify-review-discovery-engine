"""Persistent Chroma vector store for review embeddings and retrieval."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from analysis.embeddings import EMBEDDING_DIM
from utils.config import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)


def _get_client():
    import chromadb

    settings = get_settings()
    chroma_path = Path(settings.chroma_path)
    chroma_path.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(chroma_path))


def get_review_collection():
    settings = get_settings()
    client = _get_client()
    return client.get_or_create_collection(
        name=settings.chroma_collection_name,
        metadata={"hnsw:space": "cosine"},
    )


def clear_review_collection() -> None:
    settings = get_settings()
    client = _get_client()
    try:
        client.delete_collection(settings.chroma_collection_name)
    except Exception:
        logger.debug("Chroma collection did not exist; nothing to clear.")


def upsert_review_embeddings(
    *,
    review_ids: list[str],
    texts: list[str],
    embeddings: np.ndarray,
    metadatas: list[dict] | None = None,
) -> int:
    if not review_ids:
        return 0

    collection = get_review_collection()
    if metadatas is None:
        metadatas = [{} for _ in review_ids]

    collection.upsert(
        ids=review_ids,
        documents=texts,
        embeddings=embeddings.astype(float).tolist(),
        metadatas=metadatas,
    )
    return len(review_ids)


def get_embeddings_for_reviews(review_ids: list[str]) -> np.ndarray:
    if not review_ids:
        return np.empty((0, EMBEDDING_DIM), dtype=np.float32)

    collection = get_review_collection()
    result = collection.get(ids=review_ids, include=["embeddings"])
    returned_ids = result.get("ids", [])
    returned_embeddings = result.get("embeddings", [])

    embed_map = {
        review_id: np.asarray(embedding, dtype=np.float32)
        for review_id, embedding in zip(returned_ids, returned_embeddings)
    }
    ordered_vectors = [embed_map[review_id] for review_id in review_ids if review_id in embed_map]
    if not ordered_vectors:
        return np.empty((0, EMBEDDING_DIM), dtype=np.float32)
    return np.vstack(ordered_vectors)


def query_similar_review_ids(
    *,
    query_embedding: np.ndarray,
    top_k: int,
    where: dict | None = None,
) -> list[tuple[str, float]]:
    collection = get_review_collection()
    result = collection.query(
        query_embeddings=[query_embedding.astype(float).tolist()],
        n_results=top_k,
        where=where,
        include=["distances"],
    )

    ids = (result.get("ids") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    scored: list[tuple[str, float]] = []
    for review_id, distance in zip(ids, distances):
        score = max(0.0, 1.0 - float(distance))
        scored.append((review_id, score))
    return scored


def count_embeddings() -> int:
    collection = get_review_collection()
    return collection.count()
