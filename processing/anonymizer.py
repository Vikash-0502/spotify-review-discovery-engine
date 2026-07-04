"""Username anonymization."""

import hashlib

SALT = "review_discovery_engine_v1"


def anonymize_author(platform: str, author_name: str | None) -> str:
    name = (author_name or "unknown").strip() or "unknown"
    digest = hashlib.sha256(f"{SALT}:{platform}:{name}".encode()).hexdigest()[:8]
    return f"user_{digest}"
