"""PII pattern checks for pulse outputs."""

import re
from typing import Any

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b")
HANDLE_RE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{2,}")
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

SKIP_VALUE_SCAN_KEYS = {
    "id",
    "review_id",
    "theme_id",
    "run_id",
    "record_id",
    "external_id",
    "document_id",
}


def should_scan_text_field(field_name: str, text: str) -> bool:
    lowered = field_name.lower()
    if lowered in SKIP_VALUE_SCAN_KEYS or lowered.endswith("_id"):
        return False
    if UUID_RE.match(text.strip()):
        return False
    return True


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
