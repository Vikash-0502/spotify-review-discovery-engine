"""Cross-source deduplication using content fingerprints."""

import hashlib
import re

FINGERPRINT_LENGTH = 300


def content_fingerprint(content: str) -> str:
    """Create a normalized hash for duplicate detection across sources."""
    normalized = content.lower().strip()
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    snippet = normalized[:FINGERPRINT_LENGTH]
    return hashlib.sha256(snippet.encode()).hexdigest()


class DedupTracker:
    def __init__(self) -> None:
        self._seen: set[str] = set()
        self.duplicates_removed = 0

    def is_duplicate(self, content: str) -> bool:
        fp = content_fingerprint(content)
        if fp in self._seen:
            self.duplicates_removed += 1
            return True
        self._seen.add(fp)
        return False
