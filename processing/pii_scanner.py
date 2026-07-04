"""PII detection and redaction."""

import re

EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)?\d{3}[-.\s]?\d{4}\b")
URL_WITH_CREDS = re.compile(r"https?://[^\s]+@[^\s]+", re.IGNORECASE)


def contains_pii(text: str) -> bool:
    if not text:
        return False
    return bool(EMAIL_PATTERN.search(text) or PHONE_PATTERN.search(text) or URL_WITH_CREDS.search(text))


def redact_pii(text: str) -> str:
    if not text:
        return text
    cleaned = EMAIL_PATTERN.sub("[EMAIL REDACTED]", text)
    cleaned = PHONE_PATTERN.sub("[PHONE REDACTED]", cleaned)
    cleaned = URL_WITH_CREDS.sub("[URL REDACTED]", cleaned)
    return cleaned
