"""Text and timestamp normalization."""

import html
import re
import unicodedata
from datetime import datetime, timezone

WHITESPACE_PATTERN = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    if not text:
        return ""
    decoded = html.unescape(text)
    decoded = unicodedata.normalize("NFKC", decoded)
    decoded = WHITESPACE_PATTERN.sub(" ", decoded).strip()
    return decoded


def normalize_platform(platform: str) -> str:
    return platform.strip().lower().replace("-", "_")


def parse_posted_at(value: str | datetime | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def word_count(text: str) -> int:
    return len(text.split()) if text else 0
