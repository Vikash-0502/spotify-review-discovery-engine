"""Tests for Chroma → pgvector migration helpers."""

import sys
from pathlib import Path

import numpy as np
import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.migrate_sqlite_chroma_to_postgres import (  # noqa: E402
    _coerce_chroma_embeddings,
    _coerce_chroma_ids,
)


def test_coerce_chroma_ids_handles_none():
    assert _coerce_chroma_ids(None) == []


def test_coerce_chroma_embeddings_handles_none():
    assert _coerce_chroma_embeddings(None) == []


def test_coerce_chroma_embeddings_accepts_2d_numpy_array():
    embeddings = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]], dtype=np.float32)
    vectors = _coerce_chroma_embeddings(embeddings)
    assert len(vectors) == 2
    assert vectors[0] == pytest.approx([0.1, 0.2, 0.3])


def test_coerce_chroma_embeddings_accepts_1d_numpy_array():
    embeddings = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    vectors = _coerce_chroma_embeddings(embeddings)
    assert len(vectors) == 1
    assert vectors[0] == pytest.approx([0.1, 0.2, 0.3])


def test_numpy_truthiness_would_fail_without_coercion():
    embeddings = np.array([[0.1, 0.2]], dtype=np.float32)
    with pytest.raises(ValueError):
        _ = embeddings or []
