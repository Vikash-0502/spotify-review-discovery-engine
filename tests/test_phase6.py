"""Tests for Phase 6 validation and weekly pulse generation."""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from delivery.pulse import run_weekly_pulse  # noqa: E402
from models.database import get_session_factory, init_db, reset_engine  # noqa: E402
from models.schema import Quote, RawReview, Review, ReviewTheme, Theme, WeeklyPulse  # noqa: E402
from validation.validator import validate_weekly_pulse  # noqa: E402


@pytest.fixture
def phase6_db(tmp_path, monkeypatch):
    db_path = tmp_path / "phase6.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("GROQ_API_KEY", "")
    from utils.config import get_settings

    get_settings.cache_clear()
    reset_engine()
    init_db()
    yield
    reset_engine()
    get_settings.cache_clear()


def _seed_phase6_records():
    session = get_session_factory()()
    now = datetime.now(timezone.utc)
    try:
        themes: list[Theme] = []
        for idx, name in enumerate(
            [
                "Repeated recommendations",
                "Shuffle frustration",
                "Too many ads",
            ],
            start=1,
        ):
            theme = Theme(
                name=name,
                readable_name=name,
                description=f"Theme {idx} description",
                summary=f"Theme {idx} summary based on user complaints.",
                root_cause=f"Theme {idx} root cause for action planning.",
                review_count=1,
                overall_sentiment="negative",
                date_range_start=now - timedelta(days=7),
                date_range_end=now,
                top_keywords=["spotify", "discover", f"issue-{idx}"],
            )
            session.add(theme)
            themes.append(theme)
        session.flush()

        review_texts = [
            "Discover Weekly keeps repeating the same songs and I barely find new artists anymore.",
            "Shuffle mode ignores my taste and keeps playing songs I always skip.",
            "The ads interrupt discovery and make it hard to enjoy new music recommendations.",
        ]
        platforms = ["play_store", "app_store", "spotify_community"]

        for idx, (text, platform, theme) in enumerate(zip(review_texts, platforms, themes), start=1):
            raw = RawReview(
                platform=platform,
                external_id=f"raw-{idx}",
                source_url=f"https://example.com/{idx}",
                raw_payload={"body": text},
            )
            session.add(raw)
            session.flush()

            review = Review(
                raw_review_id=raw.id,
                platform=platform,
                content=text,
                title=f"Review {idx}",
                rating=1,
                posted_at=now - timedelta(days=idx),
                anonymized_author=f"user_{idx}",
                sentiment="negative",
                language="en",
                word_count=len(text.split()),
                user_segment="Active music seeker",
            )
            session.add(review)
            session.flush()

            session.add(ReviewTheme(review_id=review.id, theme_id=theme.id, membership_score=0.95))
            session.add(
                Quote(
                    review_id=review.id,
                    theme_id=theme.id,
                    excerpt=text,
                    source_platform=platform,
                    is_representative=True,
                )
            )

        session.commit()
    finally:
        session.close()


def test_validate_weekly_pulse_detects_bad_quote():
    pulse = {
        "headline": "Weekly pulse",
        "summary": "A short grounded summary.",
        "top_themes": [
            {"name": "Theme 1", "why_it_matters": "Reason 1"},
            {"name": "Theme 2", "why_it_matters": "Reason 2"},
            {"name": "Theme 3", "why_it_matters": "Reason 3"},
        ],
        "quotes": [
            {"review_id": "r1", "excerpt": "made up quote"},
            {"review_id": "r2", "excerpt": "real quote two"},
            {"review_id": "r3", "excerpt": "real quote three"},
        ],
        "actions": ["a1", "a2", "a3"],
    }
    result = validate_weekly_pulse(
        pulse,
        review_lookup={"r1": "actual review one", "r2": "real quote two", "r3": "real quote three"},
        theme_limit=3,
        quote_limit=3,
        action_limit=3,
        max_words=250,
    )
    assert result.is_valid is False
    assert any("does not match" in error for error in result.errors)


def test_run_weekly_pulse_dry_run_creates_record(phase6_db):
    _seed_phase6_records()
    result = run_weekly_pulse(dry_run=True)

    assert result.validation.is_valid is True
    assert result.delivery is not None
    assert result.delivery.status == "saved_locally"

    session = get_session_factory()()
    try:
        saved = session.query(WeeklyPulse).order_by(WeeklyPulse.created_at.desc()).first()
        assert saved is not None
        assert saved.validation_passed is True
        assert saved.document_url is not None
        assert len(saved.top_themes) == 3
        assert len(saved.quotes) == 3
        assert len(saved.actions) == 3
    finally:
        session.close()
