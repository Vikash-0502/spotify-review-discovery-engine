"""Quote provenance checks for weekly pulse payloads."""

import re


def normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def quote_matches_review(quote: str, review_text: str) -> bool:
    normalized_quote = normalize_text(quote)
    normalized_review = normalize_text(review_text)
    return normalized_quote in normalized_review


def validate_quotes_against_reviews(
    quotes: list[dict],
    review_lookup: dict[str, str],
) -> list[str]:
    errors: list[str] = []

    for idx, quote in enumerate(quotes, start=1):
        review_id = str(quote.get("review_id", "")).strip()
        excerpt = str(quote.get("excerpt", "")).strip()

        if review_id not in review_lookup:
            errors.append(f"quotes[{idx}] review_id not found in sampled review set")
            continue

        review_text = review_lookup[review_id]
        if not quote_matches_review(excerpt, review_text):
            errors.append(f"quotes[{idx}] excerpt does not match the source review text")

    return errors
