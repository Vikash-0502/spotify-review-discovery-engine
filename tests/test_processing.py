"""Tests for data processing pipeline."""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from processing.anonymizer import anonymize_author  # noqa: E402
from processing.dedup import DedupTracker, content_fingerprint  # noqa: E402
from processing.normalizer import normalize_text, parse_posted_at  # noqa: E402
from processing.pii_scanner import contains_pii, redact_pii  # noqa: E402
from processing.validation import validate_content  # noqa: E402


def test_anonymize_author_is_deterministic():
    a = anonymize_author("play_store", "JohnDoe")
    b = anonymize_author("play_store", "JohnDoe")
    c = anonymize_author("app_store", "JohnDoe")
    assert a == b
    assert a != c
    assert a.startswith("user_")


def test_pii_redaction():
    text = "Contact me at test@example.com or 555-123-4567"
    assert contains_pii(text)
    cleaned = redact_pii(text)
    assert "test@example.com" not in cleaned
    assert "555-123-4567" not in cleaned


def test_normalize_text():
    assert normalize_text("  Hello   world  ") == "Hello world"
    assert normalize_text("Tom &amp; Jerry") == "Tom & Jerry"


def test_dedup_tracker():
    dedup = DedupTracker()
    text = "Discover Weekly keeps repeating the same songs"
    assert dedup.is_duplicate(text) is False
    assert dedup.is_duplicate(text) is True
    assert dedup.duplicates_removed == 1


def test_content_fingerprint_ignores_case():
    assert content_fingerprint("Hello World!") == content_fingerprint("hello world")


def test_validate_content_rejects_short():
    result = validate_content("too short")
    assert result.ok is False


def test_parse_posted_at_utc():
    dt = parse_posted_at("2024-01-15T10:00:00Z")
    assert dt is not None
    assert dt.tzinfo is not None
