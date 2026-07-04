"""Phase 9 integration checks against the FastAPI app."""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from analysis.question_mapper import RESEARCH_QUESTIONS  # noqa: E402
from api.main import app  # noqa: E402
from validation.privacy_audit import audit_api_payload  # noqa: E402

client = TestClient(app)


def test_integration_research_questions_cover_all_six():
    response = client.get("/api/questions")
    assert response.status_code == 200
    payload = response.json()
    answers = payload["answers"]
    assert len(answers) == len(RESEARCH_QUESTIONS)
    for answer in answers:
        assert answer["question"]
        assert answer["answer_summary"]
        assert 1 <= answer["criticality_rating"] <= 5
        assert answer["supporting_review_count"] >= 0


def test_integration_search_filters_and_shape():
    response = client.get("/api/search", params={"q": "playlist", "limit": 5})
    assert response.status_code == 200
    payload = response.json()
    assert payload["query"] == "playlist"
    assert isinstance(payload["results"], list)


def test_integration_chat_endpoint_grounded_shape():
    response = client.get(
        "/api/chat",
        params={"q": "What are common recommendation frustrations?"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["question"]
    assert "answer" in payload
    assert "citations" in payload
    assert "based_on_review_count" in payload
    assert "refused" in payload


def test_integration_dashboard_core_endpoints():
    for path in (
        "/api/metrics",
        "/api/themes?limit=3",
        "/api/sentiment",
        "/api/pain-points",
        "/api/segments",
        "/api/quotes",
        "/api/pipeline/status",
    ):
        response = client.get(path)
        assert response.status_code == 200, path


def test_integration_api_no_forbidden_reviewer_keys():
    from validation.privacy_audit import audit_api_forbidden_keys

    for path, params in (
        ("/api/questions", None),
        ("/api/search", {"q": "discover", "limit": 3}),
        ("/api/themes?limit=3", None),
    ):
        response = client.get(path, params=params)
        assert response.status_code == 200
        report = audit_api_forbidden_keys(response.json(), surface=path)
        assert report.passed is True


def test_audit_api_payload_flags_pii_in_synthetic_excerpt():
    payload = {
        "answers": [
            {
                "representative_quotes": [
                    {"excerpt": "Please fix this @someuser", "review_id": "abc"},
                ]
            }
        ]
    }
    report = audit_api_payload(payload, surface="/api/questions")
    assert report.passed is False
