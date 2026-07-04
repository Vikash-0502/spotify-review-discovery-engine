"""Input validation for raw review records."""

from dataclasses import dataclass
from datetime import datetime, timezone

MIN_CONTENT_LENGTH = 20
MAX_CONTENT_LENGTH = 10000


@dataclass
class ValidationResult:
    ok: bool
    reason: str = ""


def validate_content(content: str) -> ValidationResult:
    if not content or not content.strip():
        return ValidationResult(False, "empty_content")
    if len(content.strip()) < MIN_CONTENT_LENGTH:
        return ValidationResult(False, "content_too_short")
    if len(content) > MAX_CONTENT_LENGTH:
        return ValidationResult(False, "content_too_long")
    return ValidationResult(True)


def validate_posted_at(posted_at: datetime | None) -> ValidationResult:
    if posted_at is None:
        return ValidationResult(False, "missing_date")
    if posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    if posted_at.year < 2010:
        return ValidationResult(False, "date_too_old")
    if posted_at > datetime.now(timezone.utc):
        return ValidationResult(False, "date_in_future")
    return ValidationResult(True)


def validate_platform(platform: str) -> ValidationResult:
    allowed = {"play_store", "app_store", "reddit", "spotify_community", "social_media"}
    if platform not in allowed:
        return ValidationResult(False, "invalid_platform")
    return ValidationResult(True)
