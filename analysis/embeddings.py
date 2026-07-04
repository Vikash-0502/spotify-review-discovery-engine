"""Semantic embeddings for reviews."""

import numpy as np
from sentence_transformers import SentenceTransformer

from utils.config import get_settings
from utils.logging import get_logger

logger = get_logger(__name__)

EMBEDDING_DIM = 384
_MODEL: SentenceTransformer | None = None


def get_embedding_model() -> SentenceTransformer:
    global _MODEL
    settings = get_settings()
    if _MODEL is None:
        logger.info("Loading embedding model: %s", settings.embedding_model)
        _MODEL = SentenceTransformer(settings.embedding_model)
    return _MODEL


def encode_texts(texts: list[str], batch_size: int = 64) -> np.ndarray:
    model = get_embedding_model()
    vectors = model.encode(texts, batch_size=batch_size, show_progress_bar=True)
    return np.asarray(vectors, dtype=np.float32)


def serialize_embedding(vector: np.ndarray) -> bytes:
    return vector.astype(np.float32).tobytes()


def deserialize_embedding(data: bytes) -> np.ndarray:
    return np.frombuffer(data, dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)
