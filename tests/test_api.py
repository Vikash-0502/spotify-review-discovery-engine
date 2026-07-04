import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_get_stats():
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_reviews" in data
    assert "platforms" in data

def test_get_themes():
    response = client.get("/api/themes?limit=2")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    if data:
        assert "name" in data[0]

def test_get_sentiment():
    response = client.get("/api/sentiment")
    assert response.status_code == 200
    data = response.json()
    assert "positive" in data
    assert "negative" in data

def test_get_pain_points():
    response = client.get("/api/pain-points")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_get_quotes():
    response = client.get("/api/quotes")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_get_questions():
    response = client.get("/api/questions")
    assert response.status_code == 200
    data = response.json()
    assert "platform_filter" in data
    assert "answers" in data
    assert isinstance(data["answers"], list)
    if data["answers"]:
        ans = data["answers"][0]
        assert "question" in ans
        assert "answer_summary" in ans
        assert "criticality_rating" in ans
        assert "top_themes" in ans

def test_get_questions_with_platform():
    response = client.get("/api/questions?platform=play_store")
    assert response.status_code == 200
    data = response.json()
    assert data["platform_filter"] == "play_store"


def test_get_latest_weekly_pulse():
    response = client.get("/api/weekly-pulse/latest")
    assert response.status_code == 200

