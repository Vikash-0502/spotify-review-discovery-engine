"""PII pattern checks for pulse outputs."""

import re
from typing import Any

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?:\+?\d[\d\s().-]{7,}\d)")
HANDLE_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{2,}")


def find_pii(text: str) -> list[str]:
    matches: list[str] = []
    if EMAIL_RE.search(text):
        matches.append("email")
    if PHONE_RE.search(text):
        matches.append("phone")
    if HANDLE_RE.search(text):
        matches.append("handle")
    return matches


def validate_pii(pulse: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    fields: list[tuple[str, str]] = [
        ("headline", str(pulse.get("headline", ""))),
        ("summary", str(pulse.get("summary", ""))),
    ]

    for idx, theme in enumerate(pulse.get("top_themes", []) or [], start=1):
        if isinstance(theme, dict):
            fields.append((f"top_themes[{idx}].name", str(theme.get("name", ""))))
            fields.append((f"top_themes[{idx}].why_it_matters", str(theme.get("why_it_matters", ""))))

    for idx, quote in enumerate(pulse.get("quotes", []) or [], start=1):
        if isinstance(quote, dict):
            fields.append((f"quotes[{idx}].excerpt", str(quote.get("excerpt", ""))))

    for idx, action in enumerate(pulse.get("actions", []) or [], start=1):
        fields.append((f"actions[{idx}]", str(action)))

    for field_name, text in fields:
        pii_hits = find_pii(text)
        if pii_hits:
            errors.append(f"{field_name} contains blocked PII pattern(s): {', '.join(pii_hits)}")

    return errors
