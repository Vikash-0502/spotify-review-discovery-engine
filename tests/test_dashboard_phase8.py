"""Tests for Phase 8 dashboard helper utilities."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.helpers import evidence_strength_label, render_based_on_badge, sentiment_badge  # noqa: E402


def test_evidence_strength_label_thresholds():
    assert evidence_strength_label(60) == ("High", "strength-high")
    assert evidence_strength_label(20) == ("Medium", "strength-medium")
    assert evidence_strength_label(3) == ("Low", "strength-low")


def test_render_based_on_badge():
    html = render_based_on_badge(39)
    assert "Based on 39 reviews" in html
    assert "evidence-badge" in html


def test_sentiment_badge_uses_text_labels():
    html = sentiment_badge("negative")
    assert "Negative" in html
    assert "sent-negative" in html
