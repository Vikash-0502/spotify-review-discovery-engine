"""Word-count checks for weekly pulse payloads."""

from typing import Any


def count_words(text: str) -> int:
    return len([token for token in text.split() if token.strip()])


def pulse_text(pulse: dict[str, Any]) -> str:
    pieces: list[str] = [
        str(pulse.get("headline", "")).strip(),
        str(pulse.get("summary", "")).strip(),
    ]

    for theme in pulse.get("top_themes", []) or []:
        if isinstance(theme, dict):
            pieces.append(str(theme.get("name", "")).strip())
            pieces.append(str(theme.get("why_it_matters", "")).strip())

    for quote in pulse.get("quotes", []) or []:
        if isinstance(quote, dict):
            pieces.append(str(quote.get("excerpt", "")).strip())

    for action in pulse.get("actions", []) or []:
        pieces.append(str(action).strip())

    return "\n".join(piece for piece in pieces if piece)


def validate_word_limit(pulse: dict[str, Any], max_words: int) -> tuple[int, list[str]]:
    words = count_words(pulse_text(pulse))
    if words > max_words:
        return words, [f"pulse exceeds {max_words} words ({words})"]
    return words, []
