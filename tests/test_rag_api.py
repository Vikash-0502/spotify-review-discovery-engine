"""Tests for Phase 7 RAG chat and retrieval."""

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.rag import REFUSAL_MESSAGE, answer_discovery_chat  # noqa: E402
from models.database import get_session_factory, init_db, reset_engine  # noqa: E402


@pytest.fixture
def rag_db(tmp_path, monkeypatch):
    db_path = tmp_path / "rag.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    reset_engine()
    init_db()
    session = get_session_factory()()
    yield session
    session.close()
    reset_engine()


def test_answer_discovery_chat_rejects_short_question(rag_db):
    result = answer_discovery_chat(rag_db, "a")
    assert result["refused"] is True
    assert result["based_on_review_count"] == 0


def test_answer_discovery_chat_refuses_when_no_reviews(rag_db, monkeypatch):
    monkeypatch.setattr(
        "analysis.rag.retrieve_reviews_hybrid",
        lambda *args, **kwargs: ([], 0),
    )
    result = answer_discovery_chat(rag_db, "Tell me about imaginary widget playback failures")
    assert result["refused"] is True
    assert REFUSAL_MESSAGE in result["answer"]


def test_chat_endpoint_shape():
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    response = client.get("/api/chat?q=Why do users struggle to discover new music?")
    assert response.status_code == 200
    data = response.json()
    assert data["question"]
    assert "answer" in data
    assert "refused" in data
    assert "citations" in data
    assert "criticality_rating" in data
    assert "source" in data


def test_search_endpoint_still_works():
    from fastapi.testclient import TestClient
    from api.main import app

    client = TestClient(app)
    response = client.get("/api/search?q=shuffle")
    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "shuffle"
    assert "results" in payload
