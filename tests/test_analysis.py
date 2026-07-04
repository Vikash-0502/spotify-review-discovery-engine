"""Tests for NLP analysis helpers (no model downloads)."""

import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.embeddings import cosine_similarity, serialize_embedding, deserialize_embedding  # noqa: E402
from analysis.insights import (  # noqa: E402
    build_insight_summary,
    classify_theme_insights,
    dominant_sentiment,
    opportunity_score,
    select_representative_quotes,
)
from analysis.preprocessing import is_english, is_noise, preprocess_text  # noqa: E402


def test_preprocess_text():
    assert preprocess_text("  hello   world  ") == "hello world"


def test_is_english():
    assert is_english("Discover Weekly is repetitive") is True


def test_is_noise_rejects_short():
    assert is_noise("too short") is True


def test_dominant_sentiment():
    assert dominant_sentiment(["negative", "negative", "positive"]) == "negative"


def test_opportunity_score():
    assert opportunity_score(100, "negative") > opportunity_score(100, "positive")


def test_classify_theme_insights():
    categories = classify_theme_insights(
        "repetitive discover weekly",
        ["discover", "weekly", "playlist"],
        ["play_store", "app_store", "spotify_community"],
    )
    assert "pain_point" in categories
    assert "behavior" in categories


def test_select_representative_quotes():
    reviews = [
        {"id": "1", "content": "Discover Weekly keeps repeating the same songs every week.", "sentiment": "negative", "platform": "play_store"},
        {"id": "2", "content": "Bad.", "sentiment": "negative", "platform": "app_store"},
    ]
    quotes = select_representative_quotes(reviews, max_quotes=1)
    assert len(quotes) == 1
    assert "Discover Weekly" in quotes[0]["excerpt"]


def test_embedding_serialization():
    vec = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    restored = deserialize_embedding(serialize_embedding(vec))
    assert np.allclose(vec, restored)


def test_cosine_similarity():
    a = np.array([1.0, 0.0], dtype=np.float32)
    b = np.array([1.0, 0.0], dtype=np.float32)
    assert cosine_similarity(a, b) == 1.0


def test_build_insight_summary():
    text = build_insight_summary("pain_point", "Bad Recommendations", 50, "negative", ["play_store"])
    assert "50 reviews" in text
