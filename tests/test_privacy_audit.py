"""Tests for Phase 9 privacy audit helpers."""

import sys
import uuid
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from models.schema import Quote, RawReview, Review, Theme, WeeklyPulse  # noqa: E402
from validation.privacy_audit import (  # noqa: E402
    audit_api_payload,
    audit_database,
    audit_reviews,
)


def _insert_review(session, *, content: str, author: str = "user_abc12345", external_id: str | None = None):
    raw = RawReview(
        platform="play_store",
        external_id=external_id or f"ext-{uuid.uuid4().hex}",
        raw_payload={"content": content},
    )
    session.add(raw)
    session.flush()
    review = Review(
        raw_review_id=raw.id,
        platform="play_store",
        content=content,
        posted_at=raw.collected_at,
        anonymized_author=author,
    )
    session.add(review)
    session.commit()
    return review


def test_audit_reviews_flags_pii(db_session):
    _insert_review(db_session, content="Contact me at leaked@example.com about shuffle bugs")
    report = audit_reviews(db_session)
    assert report.passed is False
    assert any("email" in finding.issue for finding in report.findings)


def test_audit_reviews_flags_bad_author_format(db_session):
    _insert_review(
        db_session,
        content="Shuffle keeps repeating the same songs.",
        author="real_username",
    )
    report = audit_reviews(db_session)
    assert report.passed is False
    assert any("anonymized_author" in finding.field for finding in report.findings)


def test_audit_api_payload_flags_forbidden_keys():
    payload = {"answers": [{"question": "Q1", "author": "someone"}]}
    report = audit_api_payload(payload, surface="/api/questions")
    assert report.passed is False
    assert any("forbidden" in finding.issue for finding in report.findings)


def test_audit_database_merges_surface_counts(db_session):
    review = _insert_review(db_session, content="I wish search surfaced more new artists.")
    theme = Theme(
        id="theme-1",
        name="Search gaps",
        description="Users want better search discovery",
        review_count=1,
        overall_sentiment="negative",
        date_range_start=review.posted_at,
        date_range_end=review.posted_at,
    )
    db_session.add(theme)
    db_session.flush()
    quote = Quote(
        review_id=review.id,
        theme_id=theme.id,
        excerpt="I wish search surfaced more new artists.",
        source_platform="play_store",
    )
    pulse = WeeklyPulse(
        run_id="run-1",
        title="Pulse",
        headline="Discovery friction remains high",
        summary="Users report repetitive recommendations.",
        top_themes=[],
        quotes=[],
        actions=[],
        model_name="test",
        prompt_version="v1",
    )
    db_session.add(quote)
    db_session.add(pulse)
    db_session.commit()

    report = audit_database(db_session)
    assert report.passed is True
    assert report.records_scanned["reviews"] >= 1
    assert report.records_scanned["quotes"] >= 1
    assert report.records_scanned["weekly_pulses"] >= 1
