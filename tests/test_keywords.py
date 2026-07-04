"""Tests for keyword filtering."""

from collectors.keywords import (
    is_discovery_related,
    is_spotify_context,
    passes_negative_filter,
)


def test_primary_keyword_match():
    text = "Discover Weekly keeps giving me the same songs every week."
    assert is_discovery_related(text) is True


def test_secondary_keyword_match():
    text = "My playlists feel repetitive and I keep hearing the same artist."
    assert is_discovery_related(text) is True


def test_no_match():
    text = "Great app, love the dark mode feature."
    assert is_discovery_related(text) is False


def test_spotify_source_relaxed():
    text = "Spotify recommendations are okay but shuffle is weird sometimes."
    assert is_discovery_related(text, spotify_source=True) is True


def test_negative_filter_blocks_billing():
    text = "Payment failed and billing support is terrible."
    assert passes_negative_filter(text) is False


def test_spotify_subreddit_context():
    assert is_spotify_context("bad algorithm", subreddit="spotify") is True
