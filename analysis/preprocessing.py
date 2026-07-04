"""Text preprocessing for NLP analysis."""

import re

SPAM_PATTERNS = [
    re.compile(r"(?i)click here"),
    re.compile(r"(?i)free money"),
    re.compile(r"(?i)subscribe to my"),
    re.compile(r"http[s]?://\S{60,}"),
]

MIN_WORDS = 5


def is_english(text: str) -> bool:
    """Simple heuristic — mostly ASCII letters."""
    if not text:
        return False
    letters = sum(c.isalpha() for c in text)
    return letters / max(len(text), 1) > 0.5


def is_noise(text: str) -> bool:
    if not text or len(text.split()) < MIN_WORDS:
        return True
    return any(pattern.search(text) for pattern in SPAM_PATTERNS)


def preprocess_text(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned
