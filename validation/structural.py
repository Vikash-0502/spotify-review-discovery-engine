"""Structural checks for weekly pulse payloads."""

from typing import Any


def validate_structure(
    pulse: dict[str, Any],
    *,
    theme_limit: int,
    quote_limit: int,
    action_limit: int,
) -> list[str]:
    errors: list[str] = []

    top_themes = pulse.get("top_themes")
    quotes = pulse.get("quotes")
    actions = pulse.get("actions")

    if not isinstance(top_themes, list):
        errors.append("top_themes must be a list")
    elif len(top_themes) != theme_limit:
        errors.append(f"top_themes must contain exactly {theme_limit} items")
    else:
        for idx, theme in enumerate(top_themes, start=1):
            if not isinstance(theme, dict):
                errors.append(f"top_themes[{idx}] must be an object")
                continue
            if not str(theme.get("name", "")).strip():
                errors.append(f"top_themes[{idx}] is missing name")
            if not str(theme.get("why_it_matters", "")).strip():
                errors.append(f"top_themes[{idx}] is missing why_it_matters")

    if not isinstance(quotes, list):
        errors.append("quotes must be a list")
    elif len(quotes) != quote_limit:
        errors.append(f"quotes must contain exactly {quote_limit} items")
    else:
        for idx, quote in enumerate(quotes, start=1):
            if not isinstance(quote, dict):
                errors.append(f"quotes[{idx}] must be an object")
                continue
            if not str(quote.get("review_id", "")).strip():
                errors.append(f"quotes[{idx}] is missing review_id")
            if not str(quote.get("excerpt", "")).strip():
                errors.append(f"quotes[{idx}] is missing excerpt")

    if not isinstance(actions, list):
        errors.append("actions must be a list")
    elif len(actions) != action_limit:
        errors.append(f"actions must contain exactly {action_limit} items")
    else:
        for idx, action in enumerate(actions, start=1):
            if not str(action).strip():
                errors.append(f"actions[{idx}] must be a non-empty string")

    if not str(pulse.get("headline", "")).strip():
        errors.append("headline is required")
    if not str(pulse.get("summary", "")).strip():
        errors.append("summary is required")

    return errors
