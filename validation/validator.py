"""Aggregate validator for weekly pulse outputs."""

from dataclasses import dataclass, field
from typing import Any

from validation.length import validate_word_limit
from validation.pii import validate_pii
from validation.provenance import validate_quotes_against_reviews
from validation.structural import validate_structure


@dataclass
class ValidationResult:
    is_valid: bool
    word_count: int
    errors: list[str] = field(default_factory=list)


def validate_weekly_pulse(
    pulse: dict[str, Any],
    *,
    review_lookup: dict[str, str],
    theme_limit: int,
    quote_limit: int,
    action_limit: int,
    max_words: int,
    max_theme_clusters: int = 5,
) -> ValidationResult:
    errors: list[str] = []

    theme_count = len(pulse.get("top_themes", []) or [])
    if theme_count > max_theme_clusters:
        errors.append(f"top_themes exceeds maximum cluster cap of {max_theme_clusters}")

    errors.extend(
        validate_structure(
            pulse,
            theme_limit=theme_limit,
            quote_limit=quote_limit,
            action_limit=action_limit,
        )
    )
    word_count, word_errors = validate_word_limit(pulse, max_words=max_words)
    errors.extend(word_errors)
    errors.extend(validate_quotes_against_reviews(pulse.get("quotes", []) or [], review_lookup))
    errors.extend(validate_pii(pulse))

    return ValidationResult(is_valid=not errors, word_count=word_count, errors=errors)
