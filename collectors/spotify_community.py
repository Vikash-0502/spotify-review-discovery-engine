"""Spotify Community forum collector (Khoros LiQL API)."""

import html
import re
import time
import urllib.parse
from datetime import datetime, timezone

import httpx

from collectors.base import CollectedRecord, SourceStats
from collectors.keywords import is_discovery_related, passes_negative_filter
from utils.logging import get_logger

logger = get_logger(__name__)

BASE_URL = "https://community.spotify.com"
SEARCH_TERMS = [
    "recommend",
    "discover weekly",
    "algorithm",
    "playlist",
    "shuffle",
    "release radar",
    "daily mix",
    "find new music",
    "repetitive",
    "song radio",
]
REQUEST_DELAY_SECONDS = 0.5
PAGE_SIZE = 100


def _strip_html(text: str) -> str:
    clean = re.sub(r"<[^>]+>", " ", text or "")
    return html.unescape(re.sub(r"\s+", " ", clean)).strip()


def _parse_post_time(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _fetch_messages(client: httpx.Client, term: str, offset: int) -> list[dict]:
    liql = (
        "SELECT id, subject, body, post_time, view_href FROM messages "
        f"WHERE body MATCHES '{term}' ORDER BY post_time DESC LIMIT {PAGE_SIZE} OFFSET {offset}"
    )
    url = f"{BASE_URL}/api/2.0/search?q={urllib.parse.quote(liql)}"
    response = client.get(url, timeout=30.0)
    response.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    data = response.json()
    if data.get("status") != "success":
        return []
    return data.get("data", {}).get("items", [])


def collect_spotify_community(max_per_term: int = 200) -> tuple[list[CollectedRecord], SourceStats]:
    stats = SourceStats(platform="spotify_community")
    records: list[CollectedRecord] = []
    seen_ids: set[str] = set()

    headers = {
        "User-Agent": "review-discovery-engine/1.0 (research project)",
        "Accept": "application/json",
    }

    with httpx.Client(headers=headers) as client:
        for term in SEARCH_TERMS:
            offset = 0
            term_count = 0

            while term_count < max_per_term:
                try:
                    items = _fetch_messages(client, term, offset)
                except Exception as exc:
                    stats.errors.append(f"'{term}' offset {offset}: {exc}")
                    logger.warning("Community fetch failed for '%s': %s", term, exc)
                    break

                if not items:
                    break

                for item in items:
                    stats.fetched += 1
                    term_count += 1
                    post_id = item.get("id")
                    if not post_id:
                        continue

                    subject = _strip_html(item.get("subject") or "")
                    body = _strip_html(item.get("body") or "")
                    content = body or subject
                    full_text = f"{subject}\n{body}".strip()

                    if len(content) < 20:
                        continue
                    if not is_discovery_related(full_text, spotify_source=True):
                        continue
                    if not passes_negative_filter(full_text):
                        continue

                    external_id = f"spotify_community_{post_id}"
                    if external_id in seen_ids:
                        continue
                    seen_ids.add(external_id)

                    posted_at = _parse_post_time(item.get("post_time"))
                    if not posted_at:
                        continue

                    stats.matched += 1
                    stats.track_dates(posted_at)

                    records.append(
                        CollectedRecord(
                            platform="spotify_community",
                            external_id=external_id,
                            content=content,
                            title=subject or None,
                            posted_at=posted_at,
                            source_url=item.get("view_href"),
                            metadata={"search_term": term},
                        )
                    )

                offset += PAGE_SIZE
                if len(items) < PAGE_SIZE:
                    break

    logger.info("Spotify Community: fetched=%s matched=%s", stats.fetched, stats.matched)
    return records, stats
